"""ngiot play sound command."""

from __future__ import annotations

from .common import NgiotExecuteCommand


class PlaySound(NgiotExecuteCommand):
    """Play sound command."""

    NAME = "playSound"
    APN = 40019

    def __init__(self) -> None:
        super().__init__({"seek": True})
