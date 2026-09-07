"""ngiot fan speed command tests."""

from __future__ import annotations

import pytest

from deebot_client.commands.ngiot.fan_speed import SetFanSpeed
from deebot_client.events import FanSpeedEvent, FanSpeedLevel

from . import assert_command, ngiot_response


@pytest.mark.parametrize(
    ("speed", "mode"),
    [
        (FanSpeedLevel.QUIET, "quiet"),
        (FanSpeedLevel.NORMAL, "auto"),
        (FanSpeedLevel.MAX, "strong"),
        (FanSpeedLevel.MAX_PLUS, "max"),
        ("quiet", "quiet"),
    ],
)
async def test_SetFanSpeed(speed: FanSpeedLevel | str, mode: str) -> None:
    level = speed if isinstance(speed, FanSpeedLevel) else FanSpeedLevel.QUIET
    await assert_command(
        SetFanSpeed(speed),
        ngiot_response(),
        FanSpeedEvent(level),
        expected_apn=50011,
        expected_data={"fanMode": mode},
    )
