from __future__ import annotations

from typing import Any

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
from deebot_client.events.water_info import (
    MopAttachedEvent,
    WaterAmount,
    WaterAmountEvent,
)
from deebot_client.models import State

from . import assert_ngiot_command

# Exact body.data from tools/NGIOT_Q287S6_PROTOCOL.md (apn=10001 comprehensive read).
_CAPTURED_BODY_DATA: dict[str, Any] = {
    "battery": 100,
    "breakCleanStatus": False,
    "chargeStatus": False,
    "childLock": False,
    "cleanArea": 0,
    "cleanCount": 1,
    "consumables": [
        {"left": 3120, "total": 12000, "type": "sideBrush"},
        {"left": 9120, "total": 18000, "type": "rollBrush"},
        {"left": 7620, "total": 9000, "type": "filter"},
        {"left": 360, "total": 1800, "type": "unitCare"},
    ],
    "disturbSwitch": False,
    "error": [0],
    "fanMode": "strong",
    "mopState": "installed",
    "pauseSwitch": False,
    "stationStatus": None,
    "stationType": None,
    "waterMode": "low",
    "workMode": "auto",
}


def _response(data: dict[str, Any]) -> dict[str, Any]:
    return {"header": {}, "body": {"data": data, "code": 0, "msg": "ok"}}


async def test_GetState_requests_the_state_fields() -> None:
    await assert_ngiot_command(
        GetState(),
        _response({"battery": 50}),
        BatteryEvent(50),
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_parses_full_captured_response() -> None:
    # No "status" field in this capture -> state is not determinable; no StateEvent.
    await assert_ngiot_command(
        GetState(),
        _response(_CAPTURED_BODY_DATA),
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
        ],
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_parses_live_default_fan_and_water() -> None:
    # Wire values observed live on a real q287s6 in its default state:
    # fanMode "auto" and waterMode "mid" (NOT "medium"). Regression for the
    # silently-dropped fan/water events found in manual testing.
    await assert_ngiot_command(
        GetState(),
        _response({"battery": 100, "fanMode": "auto", "waterMode": "mid"}),
        [
            BatteryEvent(100),
            FanSpeedEvent(FanSpeedLevel.NORMAL),
            WaterAmountEvent(WaterAmount.MEDIUM),
        ],
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_parses_volume_and_child_lock() -> None:
    # volume and childLock are read back from the same comprehensive read (the
    # set-apns 50023/50038 use this surface as their read oracle).
    await assert_ngiot_command(
        GetState(),
        _response({"volume": 8, "childLock": True}),
        [VolumeEvent(8, maximum=None), ChildLockEvent(True)],
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_docked_when_charging() -> None:
    await assert_ngiot_command(
        GetState(),
        _response({"battery": 80, "chargeStatus": True, "error": [0]}),
        [BatteryEvent(80), StateEvent(State.DOCKED), ErrorEvent(0, ERROR_CODES[0])],
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_paused() -> None:
    await assert_ngiot_command(
        GetState(),
        _response({"pauseSwitch": True, "status": "smartClean"}),
        StateEvent(State.PAUSED),
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_cleaning_from_status() -> None:
    await assert_ngiot_command(
        GetState(),
        _response({"status": "smartClean"}),
        StateEvent(State.CLEANING),
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )


async def test_GetState_error_sets_error_state() -> None:
    await assert_ngiot_command(
        GetState(),
        _response({"error": [105]}),
        [StateEvent(State.ERROR), ErrorEvent(105, ERROR_CODES[105])],
        expected_apn=10001,
        expected_data={"fields": STATE_FIELDS},
    )
