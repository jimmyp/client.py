"""Capability wiring tests for the DEEBOT NEO 2.0 PLUS (q287s6, ngiot)."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import functools
import inspect
from typing import TYPE_CHECKING

from deebot_client import hardware
from deebot_client.capabilities import DeviceType
from deebot_client.command import Command
from deebot_client.commands.json.common import JsonCommand
from deebot_client.commands.ngiot.actions import PlaySound, ResetLifeSpan
from deebot_client.commands.ngiot.common import NgiotCommand
from deebot_client.commands.ngiot.settings import SetChildLock, SetVolume
from deebot_client.commands.ngiot.state import GetState
from deebot_client.commands.ngiot.unsupported import (
    CustomCommand,
    _UnsupportedCommand,
)
from deebot_client.commands.xml.common import XmlCommand
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    ChildLockEvent,
    CustomCommandEvent,
    ErrorEvent,
    FanSpeedEvent,
    LifeSpanEvent,
    NetworkInfoEvent,
    ReportStatsEvent,
    StateEvent,
    StatsEvent,
    TotalStatsEvent,
    VolumeEvent,
)
from deebot_client.events.water_info import MopAttachedEvent, WaterAmountEvent

if TYPE_CHECKING:
    from deebot_client.events.base import Event


def _command_classes(obj: object, seen: set[int] | None = None) -> set[type[Command]]:
    """Collect every Command class reachable from a capabilities tree.

    Walks the frozen-dataclass capability tree and pulls out the command classes
    referenced by ``get`` lists and the command-bearing callables (``set``,
    ``execute``, ``reset``, ``command``, ``area``). Callables may be bare command
    classes or ``functools.partial`` wrappers; both are unwrapped to the class.
    """
    seen = seen if seen is not None else set()
    found: set[type[Command]] = set()

    def add_callable(value: object) -> None:
        target = value
        while isinstance(target, functools.partial):
            target = target.func
        if inspect.isclass(target) and issubclass(target, Command):
            found.add(target)

    if is_dataclass(obj) and not isinstance(obj, type):
        if id(obj) in seen:
            return found
        seen.add(id(obj))
        for field_ in fields(obj):
            found |= _command_classes(getattr(obj, field_.name), seen)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            if isinstance(item, Command):
                found.add(type(item))
            else:
                found |= _command_classes(item, seen)
    elif callable(obj):
        add_callable(obj)

    return found


async def test_q287s6_never_uses_a_legacy_transport_command() -> None:
    # The whole point of the ngiot work: NOTHING reachable from this profile may
    # be a legacy JSON/XML command. Those POST to iot/devmanager.do, which eco-ng
    # devices silently ignore -- the exact bug this device class hit. Every
    # command must be an ngiot command or an explicit no-op "not supported" stub.
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None

    commands = _command_classes(info.capabilities)
    assert commands, "walked the profile but found no commands -- walker is broken"

    offenders = {
        cmd.__name__
        for cmd in commands
        if not issubclass(cmd, (NgiotCommand, _UnsupportedCommand))
    }
    assert not offenders, (
        f"q287s6 wires non-ngiot command(s) that would hit a dead transport: "
        f"{sorted(offenders)}"
    )

    # And specifically: no live legacy command leaked in.
    legacy = {
        cmd.__name__ for cmd in commands if issubclass(cmd, (JsonCommand, XmlCommand))
    }
    assert not legacy, f"q287s6 still wires legacy commands: {sorted(legacy)}"


async def test_q287s6_is_recognised_as_a_vacuum() -> None:
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    assert info.capabilities.device_type == DeviceType.VACUUM


async def test_q287s6_unsupported_slots_use_ngiot_stubs() -> None:
    # custom has no captured ngiot surface, so it must use the explicit "not
    # supported yet" ngiot stub -- NOT the legacy JSON command that POSTs to a
    # transport this device ignores.
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    capabilities = info.capabilities

    assert capabilities.custom.set is CustomCommand


async def test_q287s6_captured_action_slots_use_real_ngiot_commands() -> None:
    # play_sound (apn 40019) and life-span reset (apn 50017) now have captured
    # ngiot surfaces, so they wire the real ngiot commands, not stubs.
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    capabilities = info.capabilities

    assert capabilities.play_sound.execute is PlaySound
    assert capabilities.life_span.reset is ResetLifeSpan
    assert capabilities.settings.volume is not None
    assert capabilities.settings.volume.set is SetVolume
    assert capabilities.settings.child_lock is not None
    assert capabilities.settings.child_lock.set is SetChildLock


async def test_q287s6_event_refresh_commands() -> None:
    info = await hardware.get_static_device_info("q287s6")
    assert info is not None
    capabilities = info.capabilities

    # A single GetState read feeds every device-telemetry event.
    expected: dict[type[Event], list[Command]] = {
        AvailabilityEvent: [GetState(is_available_check=True)],
        BatteryEvent: [GetState()],
        ChildLockEvent: [GetState()],
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
        VolumeEvent: [GetState()],
        WaterAmountEvent: [GetState()],
    }
    assert capabilities._events.keys() == expected.keys()
    for event, commands in expected.items():
        assert capabilities.get_refresh_commands(event) == commands, (
            f"Refresh commands don't match for {event}"
        )
