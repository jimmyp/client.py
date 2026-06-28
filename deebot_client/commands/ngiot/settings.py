"""q287s6 set commands for fan suction (apn 50011) and water level (apn 50013)."""

from __future__ import annotations

from deebot_client.events import FanSpeedLevel
from deebot_client.events.water_info import WaterAmount
from deebot_client.util import get_enum

from .common import NgiotGetCommand, NgiotSetCommand
from .state import (
    NGIOT_AMOUNT_TO_WATER_MODE,
    NGIOT_LEVEL_TO_FAN_MODE,
    GetState,
)


class SetFanSpeed(NgiotSetCommand):
    """Set the fan/suction mode (apn 50011)."""

    NAME = "setFanMode"
    APN = 50011

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding get command."""
        return GetState

    def __init__(self, speed: FanSpeedLevel | str) -> None:
        if isinstance(speed, str):
            speed = get_enum(FanSpeedLevel, speed)
        super().__init__({"fanMode": NGIOT_LEVEL_TO_FAN_MODE[speed]})


class SetWaterAmount(NgiotSetCommand):
    """Set the water flow level (apn 50013)."""

    NAME = "setWaterMode"
    APN = 50013

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding get command."""
        return GetState

    def __init__(self, amount: WaterAmount | str) -> None:
        if isinstance(amount, str):
            amount = get_enum(WaterAmount, amount)
        super().__init__({"waterMode": NGIOT_AMOUNT_TO_WATER_MODE[amount]})
