"""ngiot endpoint/control transport tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock

import orjson
from testfixtures import LogCapture

from deebot_client.ngiot_client import (
    NGIOT_ENDPOINT_CONTROL_PATH,
    NGIOT_PROTOCOL_VERSION,
    NgiotClient,
)
from deebot_client.sst_authentication import SstAuthenticator
from tests.ngiot_fakes import FakeResponse, FakeSession

if TYPE_CHECKING:
    from deebot_client.models import ApiDeviceInfo

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


def _client(session: FakeSession) -> NgiotClient:
    sst = Mock(spec_set=SstAuthenticator)
    sst.async_get_token = AsyncMock(return_value=_SST)
    return NgiotClient(session, sst)


async def test_control_posts_to_mqs_host_not_api_base() -> None:
    resp = {"header": {}, "body": {"data": {"battery": 100}, "code": 0, "msg": "ok"}}
    session = FakeSession([FakeResponse(orjson.dumps(resp))])

    result = await _client(session).control(
        device_info=_device_info(), apn=10001, data={"fields": ["battery"]}
    )

    assert result == resp
    url, _ = session.calls[0]
    assert url == f"https://{_MQS}{NGIOT_ENDPOINT_CONTROL_PATH}"
    assert "api-base" not in url


async def test_control_request_shape() -> None:
    resp = {"header": {}, "body": {"data": None, "code": 0, "msg": "ok"}}
    session = FakeSession([FakeResponse(orjson.dumps(resp))])

    await _client(session).control(
        device_info=_device_info(), apn=50011, data={"fanMode": "quiet"}
    )

    _, kwargs = session.calls[0]
    params = kwargs["params"]
    assert params["ct"] == "q"
    assert params["eid"] == "did-xyz"
    assert params["et"] == "q287s6"
    assert params["er"] == "res42"
    assert params["apn"] == "50011"
    assert params["fmt"] == "j"
    assert kwargs["headers"]["x-eco-request-id"] == params["si"]

    headers = kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {_SST}"
    assert headers["Content-Type"] == "application/octet-stream"

    payload = orjson.loads(kwargs["data"])
    assert payload["body"]["data"] == {"fanMode": "quiet"}
    assert payload["header"]["ver"] == NGIOT_PROTOCOL_VERSION
    assert payload["header"]["m"] == "request"


async def test_control_does_not_log_sst() -> None:
    resp = {"header": {}, "body": {"data": {}, "code": 0, "msg": "ok"}}
    session = FakeSession([FakeResponse(orjson.dumps(resp))])

    with LogCapture() as log:
        await _client(session).control(
            device_info=_device_info(), apn=10001, data={"fields": ["battery"]}
        )

    for record in log.records:
        assert _SST not in record.getMessage()
