from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, call

from deebot_client.authentication import Authenticator
from deebot_client.event_bus import EventBus
from deebot_client.message import HandlingResult
from deebot_client.models import ApiDeviceInfo, Credentials

if TYPE_CHECKING:
    from deebot_client.commands.ngiot.common import NgiotCommand
    from deebot_client.events import Event


def _device_info() -> ApiDeviceInfo:
    info: dict[str, Any] = {
        "class": "q287s6",
        "did": "did",
        "name": "name",
        "nick": "nick",
        "resource": "resource",
        "company": "eco-ng",
        "service": {"mqs": "api-ngiot.dc-na.ww.ecouser.net"},
    }
    return info  # type: ignore[return-value]


async def assert_ngiot_command(
    command: NgiotCommand,
    control_response: dict[str, Any],
    expected_events: Event | None | Sequence[Event],
    *,
    expected_apn: int,
    expected_data: dict[str, Any],
    handling_result: HandlingResult | None = None,
) -> None:
    """Execute an ngiot command against a mocked transport and verify behaviour."""
    handling_result = handling_result or HandlingResult.success()
    event_bus = Mock(spec_set=EventBus)

    ngiot = Mock()
    ngiot.control = AsyncMock(return_value=control_response)
    authenticator = Mock(spec_set=Authenticator)
    authenticator.authenticate = AsyncMock(
        return_value=Credentials("token", "user_id", 9999)
    )
    authenticator.ngiot = ngiot

    result, _response = await command._execute(authenticator, _device_info(), event_bus)

    # transport was addressed by numeric apn with the expected body.data
    ngiot.control.assert_awaited_once()
    kwargs = ngiot.control.await_args.kwargs
    assert kwargs["apn"] == expected_apn
    assert kwargs["data"] == expected_data

    assert result.state == handling_result.state

    if expected_events:
        if isinstance(expected_events, Sequence):
            event_bus.notify.assert_has_calls([call(x) for x in expected_events])
            assert event_bus.notify.call_count == len(expected_events)
        else:
            event_bus.notify.assert_called_once_with(expected_events)
    else:
        event_bus.notify.assert_not_called()
