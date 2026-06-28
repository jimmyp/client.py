"""Capability wiring tests for the DEEBOT NEO 2.0 PLUS (q287s6, ngiot)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deebot_client import hardware
from deebot_client.capabilities import DeviceType
from deebot_client.commands.ngiot.state import GetState
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    CustomCommandEvent,
    ErrorEvent,
    FanSpeedEvent,
    LifeSpanEvent,
    NetworkInfoEvent,
    ReportStatsEvent,
    StateEvent,
    StatsEvent,
    TotalStatsEvent,
)
from deebot_client.events.water_info import MopAttachedEvent, WaterAmountEvent

if TYPE_CHECKING:
    from deebot_client.command import Command
    from deebot_client.events.base import Event


async def test_q287s6_is_recognised_as_a_vacuum() -> None:
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    assert info.capabilities.device_type == DeviceType.VACUUM


async def test_q287s6_unsupported_slots_use_ngiot_stubs() -> None:
    # play_sound / custom / life-span reset have no captured ngiot surface, so
    # they must use the explicit "not supported yet" ngiot stubs -- NOT the
    # legacy JSON commands that POST to a transport this device ignores.
    from deebot_client.commands.ngiot.unsupported import (
        CustomCommand,
        PlaySound,
        ResetLifeSpan,
    )

    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    capabilities = info.capabilities

    assert capabilities.play_sound.execute is PlaySound
    assert capabilities.custom.set is CustomCommand
    assert capabilities.life_span.reset is ResetLifeSpan


async def test_q287s6_event_refresh_commands() -> None:
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    capabilities = info.capabilities

    # A single GetState read feeds every device-telemetry event.
    expected: dict[type[Event], list[Command]] = {
        AvailabilityEvent: [GetState(is_available_check=True)],
        BatteryEvent: [GetState()],
        CustomCommandEvent: [],
        ErrorEvent: [GetState()],
        FanSpeedEvent: [GetState()],
        LifeSpanEvent: [GetState()],
        MopAttachedEvent: [GetState()],
        NetworkInfoEvent: [],
        ReportStatsEvent: [],
        StateEvent: [GetState()],
        StatsEvent: [],
        TotalStatsEvent: [],
        WaterAmountEvent: [GetState()],
    }
    assert capabilities._events.keys() == expected.keys()
    for event, commands in expected.items():
        assert capabilities.get_refresh_commands(event) == commands, (
            f"Refresh commands don't match for {event}"
        )
