"""ngiot state command tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, call

from deebot_client.commands.ngiot.state import (
    STATE_FIELDS,
    GetState,
    handle_state_fields,
)
from deebot_client.const import ERROR_CODES
from deebot_client.event_bus import EventBus
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
from deebot_client.message import HandlingState
from deebot_client.models import State

from . import assert_ngiot_command

# captured body.data from the apn=10001 read
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
    # default state reports fanMode "auto" and waterMode "mid"
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
    # volume and childLock come back in the same read
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


def test_handle_state_fields_fans_out_events_directly() -> None:
    # The shared helper turns a body.data field dict into events without going
    # through a command, so a pushed MQTT message can reuse the same parser.
    event_bus = Mock(spec_set=EventBus)

    result = handle_state_fields(event_bus, {"battery": 100, "fanMode": "auto"})

    assert result.state == HandlingState.SUCCESS
    event_bus.notify.assert_has_calls(
        [call(BatteryEvent(100)), call(FanSpeedEvent(FanSpeedLevel.NORMAL))],
        any_order=True,
    )


def test_handle_state_fields_matches_GetState_parsing() -> None:
    # The helper must fan the captured read out to exactly the same events the
    # command does, so push and poll produce identical results.
    direct_bus = Mock(spec_set=EventBus)
    handle_state_fields(direct_bus, _CAPTURED_BODY_DATA)

    command_bus = Mock(spec_set=EventBus)
    GetState._handle_body_data_dict(command_bus, _CAPTURED_BODY_DATA)

    assert direct_bus.notify.call_args_list == command_bus.notify.call_args_list
