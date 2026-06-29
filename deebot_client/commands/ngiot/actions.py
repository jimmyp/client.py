"""q287s6 play-sound and life-span reset commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .common import NgiotExecuteCommand
from .state import NGIOT_LIFESPAN_TO_CONSUMABLE

if TYPE_CHECKING:
    from deebot_client.events import LifeSpan


class PlaySound(NgiotExecuteCommand):
    """Play sound command."""

    NAME = "playSound"
    APN = 40019

    def __init__(self) -> None:
        super().__init__({"seek": True})


class ResetLifeSpan(NgiotExecuteCommand):
    """Reset life span command."""

    NAME = "resetLifeSpan"
    APN = 50017

    def __init__(self, life_span: LifeSpan) -> None:
        super().__init__({"resetConsumable": NGIOT_LIFESPAN_TO_CONSUMABLE[life_span]})
