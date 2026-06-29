"""q287s6 clean and charge commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.events import StateEvent
from deebot_client.message import HandlingResult
from deebot_client.models import CleanAction, State

from .common import NgiotExecuteCommand

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus

# action -> (apn, body.data, optimistic state)
_CLEAN_ACTIONS: dict[CleanAction, tuple[int, dict[str, Any], State]] = {
    CleanAction.START: (
        40008,
        {"cleanSwitch": True, "cleanMode": "cleanBuilding"},
        State.CLEANING,
    ),
    CleanAction.STOP: (40002, {"cleanSwitch": False}, State.IDLE),
    CleanAction.PAUSE: (40009, {"pauseSwitch": True}, State.PAUSED),
    # resume is its own apn (40011), not 40009 inverted
    CleanAction.RESUME: (40011, {"pauseSwitch": False}, State.CLEANING),
}


class Clean(NgiotExecuteCommand):
    """Start/stop/pause/resume cleaning."""

    NAME = "clean"
    APN = 40008

    def __init__(self, action: CleanAction) -> None:
        apn, data, state = _CLEAN_ACTIONS[action]
        super().__init__(data)
        self.APN = apn
        self._optimistic_state = state

    def _handle_ok(
        self, event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        event_bus.notify(StateEvent(self._optimistic_state))
        return HandlingResult.success()


class Charge(NgiotExecuteCommand):
    """Charge command."""

    NAME = "charge"
    APN = 40013

    def __init__(self) -> None:
        super().__init__({"chargeSwitch": True})

    def _handle_ok(
        self, event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        event_bus.notify(StateEvent(State.RETURNING))
        return HandlingResult.success()
