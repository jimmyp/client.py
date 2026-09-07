"""ngiot volume command."""

from __future__ import annotations

from .common import NgiotGetCommand, NgiotSetCommand
from .state import GetState


class SetVolume(NgiotSetCommand):
    """Set volume command."""

    NAME = "setVolume"
    APN = 50023

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding get command."""
        return GetState

    def __init__(self, volume: int) -> None:
        super().__init__({"volume": volume})
