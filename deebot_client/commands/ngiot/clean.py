"""q287s6 clean action and charge commands.

Action surfaces captured live (see ``tools/NGIOT_Q287S6_PROTOCOL.md``):
start (40008), stop (40002), pause (40009) and return-to-dock (40015). The
resume payload (``pauseSwitch: false``) is the inferred inverse of pause.
"""

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
    CleanAction.RESUME: (40009, {"pauseSwitch": False}, State.CLEANING),
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
    """Return the bot to its charging dock (apn 40015)."""

    NAME = "charge"
    APN = 40015

    def __init__(self) -> None:
        super().__init__({"chargeSwitch": False})

    def _handle_ok(
        self, event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        event_bus.notify(StateEvent(State.RETURNING))
        return HandlingResult.success()
