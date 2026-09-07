from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, call

from deebot_client.authentication import Authenticator
from deebot_client.event_bus import EventBus
from deebot_client.events import StateEvent
from deebot_client.message import HandlingResult
from deebot_client.models import ApiDeviceInfo, Credentials
from tests.commands import _wrap_command

if TYPE_CHECKING:
    from deebot_client.command import Command
    from deebot_client.events import Event
    from deebot_client.models import State


def ngiot_response(data: dict[str, Any] | None = None, code: int = 0) -> dict[str, Any]:
    return {"header": {}, "body": {"data": data, "code": code, "msg": "ok"}}


async def assert_command(
    command: Command,
    response: dict[str, Any],
    expected_events: Event | Sequence[Event] | None,
    *,
    expected_apn: int,
    expected_data: dict[str, Any],
    handling_result: HandlingResult | None = None,
    last_state: State | None = None,
) -> None:
    handling_result = handling_result or HandlingResult.success()
    event_bus = Mock(spec_set=EventBus)
    event_bus.get_last_event.return_value = (
        StateEvent(last_state) if last_state is not None else None
    )
    authenticator = Mock(spec_set=Authenticator)
    authenticator.authenticate = AsyncMock(
        return_value=Credentials("token", "user_id", 9999)
    )
    authenticator.post_ngiot_control = AsyncMock(return_value=response)
    device_info = ApiDeviceInfo(
        {
            "company": "eco-ng",
            "did": "did",
            "name": "name",
            "nick": "nick",
            "resource": "resource",
            "class": "q287s6",
            "service": {"mqs": "api-ngiot.dc-na.ww.ecouser.net"},
        }
    )

    command, verify_result = _wrap_command(command)

    await command.execute(authenticator, device_info, event_bus)

    verify_result(handling_result, response)
    authenticator.post_ngiot_control.assert_awaited_once_with(
        device_info, expected_apn, expected_data
    )
    if expected_events:
        if isinstance(expected_events, Sequence):
            event_bus.notify.assert_has_calls([call(x) for x in expected_events])
            assert event_bus.notify.call_count == len(expected_events)
        else:
            event_bus.notify.assert_called_once_with(expected_events)
    else:
        event_bus.notify.assert_not_called()
