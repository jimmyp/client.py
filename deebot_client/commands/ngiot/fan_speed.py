"""ngiot fan speed command."""

from __future__ import annotations

from deebot_client.events import FanSpeedLevel
from deebot_client.util import get_enum

from .common import NgiotGetCommand, NgiotSetCommand
from .const import LEVEL_TO_FAN_MODE
from .state import GetState


class SetFanSpeed(NgiotSetCommand):
    """Set fan speed command."""

    NAME = "setFanMode"
    APN = 50011

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding get command."""
        return GetState

    def __init__(self, speed: FanSpeedLevel | str) -> None:
        if isinstance(speed, str):
            speed = get_enum(FanSpeedLevel, speed)
        super().__init__({"fanMode": LEVEL_TO_FAN_MODE[speed]})
