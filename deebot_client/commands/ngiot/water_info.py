"""ngiot water amount command."""

from __future__ import annotations

from deebot_client.events.water_info import WaterAmount
from deebot_client.util import get_enum

from .common import NgiotGetCommand, NgiotSetCommand
from .const import AMOUNT_TO_WATER_MODE
from .state import GetState


class SetWaterAmount(NgiotSetCommand):
    """Set water amount command."""

    NAME = "setWaterMode"
    APN = 50013

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding get command."""
        return GetState

    def __init__(self, amount: WaterAmount | str) -> None:
        if isinstance(amount, str):
            amount = get_enum(WaterAmount, amount)
        super().__init__({"waterMode": AMOUNT_TO_WATER_MODE[amount]})
