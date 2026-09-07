"""ngiot state command tests."""

from __future__ import annotations

from typing import Any

import pytest

from deebot_client.commands.ngiot.state import STATE_FIELDS, GetState
from deebot_client.const import ERROR_CODES
from deebot_client.events import (
    BatteryEvent,
    ChildLockEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    LifeSpan,
    LifeSpanEvent,
    StateEvent,
    VolumeEvent,
)
from deebot_client.events.network import NetworkInfoEvent
from deebot_client.events.water_info import (
    MopAttachedEvent,
    WaterAmount,
    WaterAmountEvent,
)
from deebot_client.models import State

from . import assert_command, ngiot_response

# body.data of a live apn 10001 read
_DATA: dict[str, Any] = {
    "battery": 100,
    "chargeStatus": False,
    "childLock": False,
    "consumables": [
        {"left": 3120, "total": 12000, "type": "sideBrush"},
        {"left": 9120, "total": 18000, "type": "rollBrush"},
        {"left": 7620, "total": 9000, "type": "filter"},
        {"left": 360, "total": 1800, "type": "unitCare"},
    ],
    "deviceInfo": {
        "fwVersion": "10.0.6",
        "ip": "192.168.1.2",
        "mac": "aa:bb:cc:dd:ee:ff",
        "rssi": "-52",
        "ssid": "wifi",
    },
    "error": [0],
    "fanMode": "strong",
    "mopState": "installed",
    "pauseSwitch": False,
    "waterMode": "low",
    "workMode": "auto",
}


async def _assert_state(data: dict[str, Any], expected: Any) -> None:
    await assert_command(
        GetState(),
        ngiot_response(data),
        expected,
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState() -> None:
    await _assert_state(
        _DATA,
        [
            BatteryEvent(100),
            FanSpeedEvent(FanSpeedLevel.MAX),
            WaterAmountEvent(WaterAmount.LOW),
            MopAttachedEvent(True),
            ErrorEvent(0, ERROR_CODES[0]),
            LifeSpanEvent(LifeSpan.SIDE_BRUSH, 26.0, 3120),
            LifeSpanEvent(LifeSpan.BRUSH, 50.67, 9120),
            LifeSpanEvent(LifeSpan.FILTER, 84.67, 7620),
            LifeSpanEvent(LifeSpan.UNIT_CARE, 20.0, 360),
            ChildLockEvent(False),
            NetworkInfoEvent(
                ip="192.168.1.2", ssid="wifi", rssi=-52, mac="aa:bb:cc:dd:ee:ff"
            ),
        ],
    )


async def test_GetState_default_fan_and_water() -> None:
    await _assert_state(
        {"fanMode": "auto", "waterMode": "mid"},
        [FanSpeedEvent(FanSpeedLevel.NORMAL), WaterAmountEvent(WaterAmount.MEDIUM)],
    )


async def test_GetState_settings() -> None:
    await _assert_state(
        {"volume": 8, "childLock": True},
        [VolumeEvent(8, maximum=None), ChildLockEvent(True)],
    )


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"chargeStatus": True}, State.DOCKED),
        ({"chargeStatus": True, "pauseSwitch": True}, State.DOCKED),
        ({"pauseSwitch": True, "status": "smartClean"}, State.PAUSED),
        ({"status": "smartClean"}, State.CLEANING),
        ({"status": "goCharge"}, State.RETURNING),
    ],
)
async def test_GetState_state(data: dict[str, Any], expected: State) -> None:
    await _assert_state(data, StateEvent(expected))


async def test_GetState_error() -> None:
    await _assert_state(
        {"error": [105], "chargeStatus": True},
        [StateEvent(State.ERROR), ErrorEvent(105, ERROR_CODES[105])],
    )


async def test_GetState_unmapped_values_are_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _assert_state(
        {"status": "napping", "fanMode": "turbo", "waterMode": "flood", "battery": 9},
        BatteryEvent(9),
    )
    messages = [r.getMessage() for r in caplog.records if r.levelname == "DEBUG"]
    assert any("napping" in m for m in messages)
    assert any("turbo" in m for m in messages)
    assert any("flood" in m for m in messages)


async def test_GetState_malformed_consumable_is_skipped() -> None:
    await _assert_state(
        {
            "consumables": [
                {"left": None, "total": 100, "type": "filter"},
                {"total": 0, "left": 0, "type": "sideBrush"},
                {"type": "unknown", "left": 1, "total": 2},
                {"left": 50, "total": 100, "type": "rollBrush"},
            ]
        },
        LifeSpanEvent(LifeSpan.BRUSH, 50.0, 50),
    )


async def test_GetState_incomplete_device_info_is_skipped() -> None:
    await _assert_state(
        {"deviceInfo": {"ip": "1.2.3.4"}, "battery": 1}, BatteryEvent(1)
    )
