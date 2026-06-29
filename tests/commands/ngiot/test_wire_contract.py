"""Wire-contract tests for q287s6 ngiot commands.

The other ngiot command tests (``assert_ngiot_command``) stop at the mocked
``Authenticator.ngiot.control`` boundary -- they prove a command passes the
right ``apn``/``data`` to the transport, but not what the transport actually
serialises onto the wire. These tests close that gap: each real command class
is driven through the *real* :class:`NgiotClient` (over a fake aiohttp session),
and the captured HTTP request is asserted against the exact payloads captured
live from the official app (see ``tools/NGIOT_Q287S6_PROTOCOL.md``).

This is the layer that catches command->wire regressions such as the
resume-apn (40011, not 40009) and dock-apn (40013 ``chargeSwitch:true``, not
40015) bugs found in manual testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self
from unittest.mock import AsyncMock, Mock

import orjson
import pytest

from deebot_client.authentication import Authenticator
from deebot_client.commands.ngiot.actions import PlaySound, ResetLifeSpan
from deebot_client.commands.ngiot.clean import Charge, Clean
from deebot_client.commands.ngiot.settings import (
    SetChildLock,
    SetFanSpeed,
    SetVolume,
    SetWaterAmount,
)
from deebot_client.commands.ngiot.state import GetState
from deebot_client.event_bus import EventBus
from deebot_client.events import FanSpeedLevel, LifeSpan
from deebot_client.events.water_info import WaterAmount
from deebot_client.models import ApiDeviceInfo, CleanAction, Credentials
from deebot_client.ngiot_client import (
    NGIOT_ENDPOINT_CONTROL_PATH,
    NgiotClient,
)
from deebot_client.sst_authentication import SstAuthenticator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deebot_client.commands.ngiot.common import NgiotCommand

_SST = "SST.header.payload.signature"
_MQS = "api-ngiot.dc-na.ww.ecouser.net"


def _device_info() -> ApiDeviceInfo:
    info: dict[str, Any] = {
        "class": "q287s6",
        "did": "did-xyz",
        "name": "name",
        "resource": "res42",
        "company": "eco-ng",
        "service": {"mqs": _MQS},
    }
    return info  # type: ignore[return-value]


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload

    def raise_for_status(self) -> None:
        return None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


class _FakeSession:
    def __init__(self, responses: Sequence[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append((url, kwargs))
        return self._responses.pop(0)


def _authenticator_over(session: _FakeSession) -> Authenticator:
    """Real NgiotClient over a fake session, exposed via a stubbed Authenticator."""
    sst = Mock(spec_set=SstAuthenticator)
    sst.async_get_token = AsyncMock(return_value=_SST)
    client = NgiotClient(session, sst)  # type: ignore[arg-type]

    auth = Mock(spec_set=Authenticator)
    auth.authenticate = AsyncMock(return_value=Credentials("token", "user_id", 9999))
    auth.ngiot = client
    return auth


async def _run(command: NgiotCommand) -> dict[str, Any]:
    """Execute a command end-to-end and return the captured POST kwargs (+url)."""
    ok = {"header": {}, "body": {"data": None, "code": 0, "msg": "ok"}}
    session = _FakeSession([_FakeResponse(orjson.dumps(ok))])
    auth = _authenticator_over(session)
    event_bus = Mock(spec_set=EventBus)

    await command._execute(auth, _device_info(), event_bus)

    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    kwargs = dict(kwargs)
    kwargs["url"] = url
    kwargs["_body"] = orjson.loads(kwargs["data"])
    return kwargs


# (command, expected apn, expected body.data) -- exactly as captured from the app.
_WIRE_CONTRACT = [
    pytest.param(
        Clean(CleanAction.START),
        "40008",
        {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
        id="start",
    ),
    pytest.param(Clean(CleanAction.STOP), "40002", {"cleanSwitch": False}, id="stop"),
    pytest.param(Clean(CleanAction.PAUSE), "40009", {"pauseSwitch": True}, id="pause"),
    pytest.param(
        Clean(CleanAction.RESUME), "40011", {"pauseSwitch": False}, id="resume"
    ),
    pytest.param(Charge(), "40013", {"chargeSwitch": True}, id="charge"),
    pytest.param(
        SetFanSpeed(FanSpeedLevel.QUIET), "50011", {"fanMode": "quiet"}, id="fan-quiet"
    ),
    pytest.param(
        SetFanSpeed(FanSpeedLevel.MAX), "50011", {"fanMode": "strong"}, id="fan-strong"
    ),
    pytest.param(
        SetWaterAmount(WaterAmount.HIGH),
        "50013",
        {"waterMode": "high"},
        id="water-high",
    ),
    pytest.param(
        SetWaterAmount(WaterAmount.MEDIUM),
        "50013",
        {"waterMode": "mid"},
        id="water-mid",
    ),
    pytest.param(SetVolume(8), "50023", {"volume": 8}, id="volume"),
    pytest.param(PlaySound(), "40019", {"seek": True}, id="play-sound"),
    pytest.param(SetChildLock(True), "50038", {"childLock": True}, id="child-lock"),
    # The resetConsumable type comes from the explicit LifeSpan->name map, NOT
    # life_span.value (LifeSpan.BRUSH.value is "brush", FILTER.value is "heap").
    pytest.param(
        ResetLifeSpan(LifeSpan.BRUSH),
        "50017",
        {"resetConsumable": "rollBrush"},
        id="reset-brush",
    ),
    pytest.param(
        ResetLifeSpan(LifeSpan.FILTER),
        "50017",
        {"resetConsumable": "filter"},
        id="reset-filter",
    ),
]


@pytest.mark.parametrize(("command", "expected_apn", "expected_data"), _WIRE_CONTRACT)
async def test_command_emits_captured_wire_payload(
    command: NgiotCommand,
    expected_apn: str,
    expected_data: dict[str, Any],
) -> None:
    kwargs = await _run(command)

    # Right host + path (the mqs host, not api-base -- #1569 fix).
    assert kwargs["url"] == f"https://{_MQS}{NGIOT_ENDPOINT_CONTROL_PATH}"

    # Right numeric surface id on the query string.
    assert kwargs["params"]["apn"] == expected_apn
    assert kwargs["params"]["et"] == "q287s6"
    assert kwargs["params"]["fmt"] == "j"

    # Right body.data -- the exact bytes the device expects.
    assert kwargs["_body"]["body"]["data"] == expected_data

    # Octet-stream JSON envelope + SST bearer.
    assert kwargs["headers"]["Content-Type"] == "application/octet-stream"
    assert kwargs["headers"]["Authorization"] == f"Bearer {_SST}"


async def test_get_state_emits_field_query_on_the_wire() -> None:
    # Reads use body.data = {"fields": [...]} against apn 10001.
    kwargs = await _run(GetState())
    assert kwargs["params"]["apn"] == "10001"
    body_data = kwargs["_body"]["body"]["data"]
    assert "fields" in body_data
    assert "battery" in body_data["fields"]
