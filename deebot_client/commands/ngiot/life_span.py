"""ngiot life span command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .common import NgiotExecuteCommand
from .const import LIFE_SPAN_TO_CONSUMABLE

if TYPE_CHECKING:
    from deebot_client.events import LifeSpan


class ResetLifeSpan(NgiotExecuteCommand):
    """Reset life span command."""

    NAME = "resetLifeSpan"
    APN = 50017

    def __init__(self, life_span: LifeSpan) -> None:
        if (consumable := LIFE_SPAN_TO_CONSUMABLE.get(life_span)) is None:
            # repr names the member; a LifeSpan formats as its bare value
            msg = f"{life_span!r} is not supported"
            raise ValueError(msg)
        super().__init__({"resetConsumable": consumable})
