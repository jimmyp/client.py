"""Tests for the ngiot 'not supported yet' stub commands.

These cover capability slots that q287s6 requires by schema but for which no
real ngiot ``endpoint/control`` surface has been captured. The stubs must NOT
hit the network (neither the ngiot transport nor the legacy portal), must
report the device as not reached, and must log a clear warning.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock

import pytest

from deebot_client.authentication import Authenticator
from deebot_client.commands.ngiot.unsupported import (
    CustomCommand,
    PlaySound,
    ResetLifeSpan,
)
from deebot_client.event_bus import EventBus
from deebot_client.events import LifeSpan
from deebot_client.models import ApiDeviceInfo, Credentials

if TYPE_CHECKING:
    from deebot_client.command import Command


def _device_info() -> ApiDeviceInfo:
    info: dict[str, Any] = {
        "class": "q287s6",
        "did": "did-xyz",
        "name": "name",
        "resource": "res42",
        "company": "eco-ng",
        "service": {"mqs": "api-ngiot.dc-na.ww.ecouser.net"},
    }
    return info  # type: ignore[return-value]


def _authenticator() -> tuple[Authenticator, Mock]:
    ngiot = Mock()
    ngiot.control = AsyncMock()
    auth = Mock(spec_set=Authenticator)
    auth.authenticate = AsyncMock(return_value=Credentials("token", "user_id", 9999))
    auth.ngiot = ngiot
    auth.post_authenticated = AsyncMock()
    return auth, ngiot


_STUBS = [
    pytest.param(PlaySound(), "playSound", id="play-sound"),
    pytest.param(CustomCommand("getFoo"), "getFoo", id="custom"),
    pytest.param(ResetLifeSpan(LifeSpan.BRUSH), "resetLifeSpan", id="lifespan-reset"),
]


@pytest.mark.parametrize(("command", "expected_name"), _STUBS)
async def test_unsupported_stub_makes_no_network_call_and_warns(
    command: Command,
    expected_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    auth, ngiot = _authenticator()
    event_bus = Mock(spec_set=EventBus)

    with caplog.at_level(logging.WARNING):
        result = await command.execute(auth, _device_info(), event_bus)

    # No network: neither the ngiot transport nor the legacy portal is touched.
    ngiot.control.assert_not_awaited()
    auth.post_authenticated.assert_not_awaited()

    # The device was not reached (the stub did nothing real).
    assert result.device_reached is False

    # And it said so, clearly, naming the device class.
    assert any(
        "not supported" in r.message.lower() and "q287s6" in r.message
        for r in caplog.records
    )
    assert expected_name == command.NAME
