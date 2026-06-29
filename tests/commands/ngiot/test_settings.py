"""ngiot fan, water, volume and child-lock set command tests."""

from __future__ import annotations

from typing import Any

import pytest

from deebot_client.commands.ngiot.settings import (
    SetChildLock,
    SetFanSpeed,
    SetVolume,
    SetWaterAmount,
)
from deebot_client.commands.ngiot.state import GetState
from deebot_client.events import (
    ChildLockEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    VolumeEvent,
)
from deebot_client.events.water_info import WaterAmount, WaterAmountEvent

from . import assert_ngiot_command

_OK: dict[str, Any] = {"header": {}, "body": {"data": None, "code": 0, "msg": "ok"}}


@pytest.mark.parametrize(
    ("value", "expected_mode", "expected_level"),
    [
        (FanSpeedLevel.QUIET, "quiet", FanSpeedLevel.QUIET),
        (FanSpeedLevel.MAX, "strong", FanSpeedLevel.MAX),
        ("max", "strong", FanSpeedLevel.MAX),
    ],
)
async def test_SetFanSpeed(
    value: FanSpeedLevel | str, expected_mode: str, expected_level: FanSpeedLevel
) -> None:
    command = SetFanSpeed(value)
    assert command.get_command is GetState
    await assert_ngiot_command(
        command,
        _OK,
        FanSpeedEvent(expected_level),
        expected_apn=50011,
        expected_data={"fanMode": expected_mode},
    )


@pytest.mark.parametrize(
    ("value", "expected_mode", "expected_amount"),
    [
        (WaterAmount.LOW, "low", WaterAmount.LOW),
        (WaterAmount.HIGH, "high", WaterAmount.HIGH),
        ("high", "high", WaterAmount.HIGH),
    ],
)
async def test_SetWaterAmount(
    value: WaterAmount | str, expected_mode: str, expected_amount: WaterAmount
) -> None:
    await assert_ngiot_command(
        SetWaterAmount(value),
        _OK,
        WaterAmountEvent(expected_amount),
        expected_apn=50013,
        expected_data={"waterMode": expected_mode},
    )


async def test_SetVolume() -> None:
    command = SetVolume(8)
    assert command.get_command is GetState
    await assert_ngiot_command(
        command,
        _OK,
        VolumeEvent(8, maximum=None),
        expected_apn=50023,
        expected_data={"volume": 8},
    )


@pytest.mark.parametrize("enable", [True, False])
async def test_SetChildLock(enable: bool) -> None:
    command = SetChildLock(enable)
    assert command.get_command is GetState
    await assert_ngiot_command(
        command,
        _OK,
        ChildLockEvent(enable),
        expected_apn=50038,
        expected_data={"childLock": enable},
    )
