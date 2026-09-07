"""ngiot custom command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.events import CustomCommandEvent
from deebot_client.message import HandlingResult

from .common import NgiotExecuteCommand

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus


class CustomCommand(NgiotExecuteCommand):
    """Custom command addressing an apn that is not part of this library."""

    NAME: str = "CustomCommand"
    APN = 0

    def __init__(
        self, name: str, args: dict[str, Any] | list[Any] | None = None
    ) -> None:
        # the name is the numeric apn
        self.NAME = name
        super().__init__(args, apn=int(name))

    def _handle_ok(
        self, event_bus: EventBus, response: dict[str, Any]
    ) -> HandlingResult:
        event_bus.notify(CustomCommandEvent(self.NAME, response))
        return HandlingResult.success()

    def __eq__(self, obj: object) -> bool:
        if super().__eq__(obj) and isinstance(obj, CustomCommand):
            return self.NAME == obj.NAME

        return False

    def __hash__(self) -> int:
        # not delegating to Command.__hash__, which hashes the (dict) args
        return hash(self.NAME)
