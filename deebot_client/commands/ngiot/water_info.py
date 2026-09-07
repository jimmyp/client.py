"""ngiot water amount command."""

from __future__ import annotations

from deebot_client.events.water_info import WaterAmount
from deebot_client.util import get_enum

from .common import NgiotSetCommand
from .const import AMOUNT_TO_WATER_MODE
from .state import GetState


class SetWaterAmount(NgiotSetCommand):
    """Set water amount command."""

    NAME = "setWaterMode"
    APN = 50013
    get_command = GetState

    def __init__(self, amount: WaterAmount | str) -> None:
        if isinstance(amount, str):
            amount = get_enum(WaterAmount, amount)
        super().__init__({"waterMode": AMOUNT_TO_WATER_MODE[amount]})
