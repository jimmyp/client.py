"""DEEBOT NEO 2.0 PLUS (q287s6) Capabilities."""

from __future__ import annotations

from deebot_client.capabilities import (
    Capabilities,
    CapabilityClean,
    CapabilityCleanAction,
    CapabilityCustomCommand,
    CapabilityEvent,
    CapabilityExecute,
    CapabilityLifeSpan,
    CapabilitySet,
    CapabilitySetEnable,
    CapabilitySettings,
    CapabilitySetTypes,
    CapabilityStats,
    CapabilityWater,
    DeviceType,
)
from deebot_client.commands.ngiot.actions import PlaySound, ResetLifeSpan
from deebot_client.commands.ngiot.clean import Charge, Clean
from deebot_client.commands.ngiot.settings import (
    SetChildLock,
    SetFanSpeed,
    SetVolume,
    SetWaterAmount,
)
from deebot_client.commands.ngiot.state import GetState
from deebot_client.commands.ngiot.unsupported import CustomCommand
from deebot_client.const import DataType
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    ChildLockEvent,
    CustomCommandEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    LifeSpan,
    LifeSpanEvent,
    NetworkInfoEvent,
    ReportStatsEvent,
    StateEvent,
    StatsEvent,
    TotalStatsEvent,
    VolumeEvent,
    water_info,
)
from deebot_client.models import StaticDeviceInfo


def get_device_info() -> StaticDeviceInfo:
    """Get device info for this model."""
    return StaticDeviceInfo(
        DataType.JSON,
        Capabilities(
            device_type=DeviceType.VACUUM,
            availability=CapabilityEvent(
                AvailabilityEvent, [GetState(is_available_check=True)]
            ),
            battery=CapabilityEvent(BatteryEvent, [GetState()]),
            charge=CapabilityExecute(Charge),
            clean=CapabilityClean(action=CapabilityCleanAction(command=Clean)),
            custom=CapabilityCustomCommand(
                event=CustomCommandEvent, get=[], set=CustomCommand
            ),
            error=CapabilityEvent(ErrorEvent, [GetState()]),
            fan_speed=CapabilitySetTypes(
                event=FanSpeedEvent,
                get=[GetState()],
                set=SetFanSpeed,
                types=(
                    FanSpeedLevel.QUIET,
                    FanSpeedLevel.NORMAL,
                    FanSpeedLevel.MAX,
                    FanSpeedLevel.MAX_PLUS,
                ),
            ),
            life_span=CapabilityLifeSpan(
                types=(
                    LifeSpan.BRUSH,
                    LifeSpan.FILTER,
                    LifeSpan.SIDE_BRUSH,
                    LifeSpan.UNIT_CARE,
                ),
                event=LifeSpanEvent,
                get=[GetState()],
                reset=ResetLifeSpan,
            ),
            network=CapabilityEvent(NetworkInfoEvent, []),
            play_sound=CapabilityExecute(PlaySound),
            settings=CapabilitySettings(
                child_lock=CapabilitySetEnable(
                    ChildLockEvent, [GetState()], SetChildLock
                ),
                volume=CapabilitySet(VolumeEvent, [GetState()], SetVolume),
            ),
            state=CapabilityEvent(StateEvent, [GetState()]),
            stats=CapabilityStats(
                clean=CapabilityEvent(StatsEvent, []),
                report=CapabilityEvent(ReportStatsEvent, []),
                total=CapabilityEvent(TotalStatsEvent, []),
            ),
            water=CapabilityWater(
                amount=CapabilitySetTypes(
                    event=water_info.WaterAmountEvent,
                    get=[GetState()],
                    set=SetWaterAmount,
                    types=(
                        water_info.WaterAmount.LOW,
                        water_info.WaterAmount.MEDIUM,
                        water_info.WaterAmount.HIGH,
                    ),
                ),
                mop_attached=CapabilityEvent(water_info.MopAttachedEvent, [GetState()]),
            ),
        ),
    )
