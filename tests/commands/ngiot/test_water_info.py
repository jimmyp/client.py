"""ngiot water amount command tests."""

from __future__ import annotations

import pytest

from deebot_client.commands.ngiot.water_info import SetWaterAmount
from deebot_client.events.water_info import WaterAmount, WaterAmountEvent

from . import assert_command, ngiot_response


@pytest.mark.parametrize(
    ("amount", "mode"),
    [
        (WaterAmount.LOW, "low"),
        (WaterAmount.MEDIUM, "mid"),
        (WaterAmount.HIGH, "high"),
        ("low", "low"),
    ],
)
async def test_SetWaterAmount(amount: WaterAmount | str, mode: str) -> None:
    expected = amount if isinstance(amount, WaterAmount) else WaterAmount.LOW
    await assert_command(
        SetWaterAmount(amount),
        ngiot_response(),
        WaterAmountEvent(expected),
        expected_apn=50013,
        expected_data={"waterMode": mode},
    )
