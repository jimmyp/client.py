"""DEEBOT NEO 2.0 PLUS (q287s6) capabilities.

This is the first ``eco-ng`` / ngiot device wired into the library: it is driven
through the ``endpoint/control`` transport (see :mod:`deebot_client.ngiot_client`)
addressing numeric ``apn`` surfaces, not the legacy ``iot/devmanager.do`` portal
endpoint. All telemetry comes from a single comprehensive read
(:class:`~deebot_client.commands.ngiot.state.GetState`, apn 10001).

Verified live against a real device (see ``tools/NGIOT_Q287S6_PROTOCOL.md``):
state read, start/stop/pause, return-to-dock, set fan and set water.

Not yet implemented for ngiot (vacuum control first): map and station telemetry.
The play-sound / custom / life-span-reset slots are required by the capability
schema but have no captured ngiot surface, so they use the explicit
``commands.ngiot.unsupported`` stubs: they make no network call, report the
device as not reached, and log a warning. They will be swapped for real ngiot
commands once their surfaces are captured.
"""

from __future__ import annotations

from deebot_client.capabilities import (
    Capabilities,
    CapabilityClean,
    CapabilityCleanAction,
    CapabilityCustomCommand,
    CapabilityEvent,
    CapabilityExecute,
    CapabilityLifeSpan,
    CapabilitySettings,
    CapabilitySetTypes,
    CapabilityStats,
    CapabilityWater,
    DeviceType,
)
from deebot_client.commands.ngiot.clean import Charge, Clean
from deebot_client.commands.ngiot.settings import SetFanSpeed, SetWaterAmount
from deebot_client.commands.ngiot.state import GetState
from deebot_client.commands.ngiot.unsupported import (
    CustomCommand,
    PlaySound,
    ResetLifeSpan,
)
from deebot_client.const import DataType
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
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
            settings=CapabilitySettings(),
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
