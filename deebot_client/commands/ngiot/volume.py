"""ngiot volume command."""

from __future__ import annotations

from .common import NgiotSetCommand
from .state import GetState


class SetVolume(NgiotSetCommand):
    """Set volume command."""

    NAME = "setVolume"
    APN = 50023
    get_command = GetState

    def __init__(self, volume: int) -> None:
        super().__init__({"volume": volume})
