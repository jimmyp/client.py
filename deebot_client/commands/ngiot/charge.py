"""ngiot charge command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.events import StateEvent
from deebot_client.message import HandlingResult
from deebot_client.models import State

from .common import NgiotExecuteCommand

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus


class Charge(NgiotExecuteCommand):
    """Charge command."""

    NAME = "charge"
    APN = 40013

    def __init__(self) -> None:
        super().__init__({"chargeSwitch": True})

    def _handle_ok(
        self, event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        # no push channel; publish the new state now
        event_bus.notify(StateEvent(State.RETURNING))
        return HandlingResult.success()
