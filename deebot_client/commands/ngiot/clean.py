"""ngiot clean command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.events import StateEvent
from deebot_client.message import HandlingResult
from deebot_client.models import CleanAction, State

from .common import NgiotExecuteCommand

if TYPE_CHECKING:
    from deebot_client.authentication import Authenticator
    from deebot_client.event_bus import EventBus
    from deebot_client.models import ApiDeviceInfo

# action -> (apn, body.data, state after success)
_CLEAN_ACTIONS: dict[CleanAction, tuple[int, dict[str, Any], State]] = {
    CleanAction.START: (
        40008,
        {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
        State.CLEANING,
    ),
    CleanAction.STOP: (40002, {"cleanSwitch": False}, State.IDLE),
    CleanAction.PAUSE: (40009, {"pauseSwitch": True}, State.PAUSED),
    CleanAction.RESUME: (40011, {"pauseSwitch": False}, State.CLEANING),
}


class Clean(NgiotExecuteCommand):
    """Clean command."""

    NAME = "clean"
    # overridden per action; present for the class-variable check
    APN = 40008

    def __init__(self, action: CleanAction) -> None:
        apn, data, self._state = _CLEAN_ACTIONS[action]
        super().__init__(dict(data), apn=apn)
        self._action = action

    async def _execute(
        self,
        authenticator: Authenticator,
        device_info: ApiDeviceInfo,
        event_bus: EventBus,
    ) -> tuple[HandlingResult, dict[str, Any]]:
        state = event_bus.get_last_event(StateEvent)
        if state is not None:
            if self._action == CleanAction.RESUME and state.state != State.PAUSED:
                self._set_action(CleanAction.START)
            elif self._action == CleanAction.START and state.state == State.PAUSED:
                self._set_action(CleanAction.RESUME)

        return await super()._execute(authenticator, device_info, event_bus)

    def _set_action(self, action: CleanAction) -> None:
        self._action = action
        apn, data, self._state = _CLEAN_ACTIONS[action]
        self._apn = apn
        self._args = dict(data)

    def _handle_ok(
        self, event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        # the device has no push channel; publish the new state now instead of
        # showing the old one until the next poll
        event_bus.notify(StateEvent(self._state))
        return HandlingResult.success()
