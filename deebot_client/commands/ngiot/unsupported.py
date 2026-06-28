"""'Not supported yet' stubs for q287s6 capability slots without an ngiot surface.

Some capabilities are required by the :class:`~deebot_client.capabilities.Capabilities`
schema but have no captured ngiot ``endpoint/control`` surface on q287s6 (e.g.
play-sound, the life-span reset action, and the generic custom command). Wiring
them to their legacy JSON commands would POST to ``iot/devmanager.do`` -- a
transport these ``eco-ng`` devices do not answer on -- so the call would fail
silently after a pointless round-trip.

These stubs make that explicit instead: they perform no network request, report
the device as not reached, and log a clear warning. Swap a stub for a real
:mod:`deebot_client.commands.ngiot` command once its surface is captured.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from deebot_client.command import Command
from deebot_client.const import DataType
from deebot_client.logging_filter import get_logger
from deebot_client.message import HandlingResult, HandlingState

if TYPE_CHECKING:
    from deebot_client.authentication import Authenticator
    from deebot_client.event_bus import EventBus
    from deebot_client.events import LifeSpan
    from deebot_client.models import ApiDeviceInfo

_LOGGER = get_logger(__name__)


class _UnsupportedCommand(Command, ABC):
    """A command that is not supported on ngiot devices yet (no-op, no network)."""

    DATA_TYPE = DataType.JSON
    _targets_bot = False

    def _get_payload(self) -> dict[str, Any]:
        return {}

    async def _execute(
        self,
        _authenticator: Authenticator,
        device_info: ApiDeviceInfo,
        _event_bus: EventBus,
    ) -> tuple[HandlingResult, dict[str, Any]]:
        _LOGGER.warning(
            'Command "%s" is not supported yet on ngiot device %s; '
            "no ngiot surface has been captured for it.",
            self.NAME,
            device_info["class"],
        )
        return HandlingResult(HandlingState.FAILED), {}

    def _handle_response(
        self, _event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        return HandlingResult(HandlingState.FAILED)


class PlaySound(_UnsupportedCommand):
    """Play-sound / locate -- no ngiot surface captured yet."""

    NAME = "playSound"


class CustomCommand(_UnsupportedCommand):
    """Custom command escape hatch -- not routable over ngiot yet."""

    NAME = "CustomCommand"

    def __init__(
        self, name: str, args: dict[str, Any] | list[Any] | None = None
    ) -> None:
        self.NAME = name
        super().__init__(args)


class ResetLifeSpan(_UnsupportedCommand):
    """Life-span counter reset -- no ngiot surface captured yet."""

    NAME = "resetLifeSpan"

    def __init__(self, life_span: LifeSpan) -> None:
        super().__init__({"type": life_span.value})
