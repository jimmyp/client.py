"""Live check of the q287s6 ngiot commands against a real device.

Credentials come from the environment: ECOVACS_USERNAME, ECOVACS_PASSWORD,
ECOVACS_COUNTRY. Uses the library's normal TLS-verified session.

    python tools/ngiot_q287s6_live.py            # read-only: GetState + CustomCommand read
    python tools/ngiot_q287s6_live.py --cycle    # MOVES THE BOT: start, pause, start(=resume), dock

The --cycle run exercises the paths changed in review: the Home Assistant
"start while paused" swap, the goCharge read-back, and pause-then-dock.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

import aiohttp

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.commands.ngiot.charge import Charge
from deebot_client.commands.ngiot.clean import Clean
from deebot_client.commands.ngiot.custom import CustomCommand
from deebot_client.commands.ngiot.state import GetState
from deebot_client.events import NetworkInfoEvent, StateEvent
from deebot_client.events.base import Event
from deebot_client.models import CleanAction, State
from deebot_client.util import md5

TARGET = "q287s6"


class _Recorder:
    """Minimal EventBus stand-in that records the events a command emits."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def notify(self, event: Event, *_: Any, **__: Any) -> None:
        self.events.append(event)
        print(f"  event: {event}", flush=True)

    def get_last_event(self, event_type: type[Event]) -> Event | None:
        for event in reversed(self.events):
            if isinstance(event, event_type):
                return event
        return None


async def _read(auth: Authenticator, info: Any, bus: _Recorder, label: str) -> State | None:
    print(f"\n[{label}] GetState:", flush=True)
    await GetState().execute(auth, info, bus)  # type: ignore[arg-type]
    state = bus.get_last_event(StateEvent)
    return state.state if isinstance(state, StateEvent) else None


async def _wait_for(
    auth: Authenticator, info: Any, bus: _Recorder, wanted: set[State], label: str
) -> State | None:
    for _ in range(12):
        state = await _read(auth, info, bus, label)
        if state in wanted:
            return state
        await asyncio.sleep(5)
    return state


async def main() -> None:
    cycle = "--cycle" in sys.argv[1:]

    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ["ECOVACS_COUNTRY"]
    device_id = md5(str(time.time()))

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=device_id, alpha_2_country=country)
        auth = Authenticator(rest, user, md5(pw))
        api = ApiClient(auth)

        devices = await api.get_devices()
        device = next((d for d in devices.mqtt if d.api.get("class") == TARGET), None)
        if device is None:
            print(f"No {TARGET} found. Supported: {[d.api.get('class') for d in devices.mqtt]}")
            return
        info = device.api
        print(f"Found {TARGET}", flush=True)

        bus = _Recorder()
        state = await _read(auth, info, bus, "1 read")
        network = bus.get_last_event(NetworkInfoEvent)
        print(f"  CHECK network event present: {isinstance(network, NetworkInfoEvent)}")

        print("\n[2] CustomCommand('10001', fields=[battery]):", flush=True)
        await CustomCommand("10001", {"fields": ["battery"]}).execute(auth, info, _Recorder())  # type: ignore[arg-type]

        if not cycle:
            print("\nRead-only run complete. Pass --cycle to drive the bot.")
            return

        if state != State.DOCKED:
            print(f"\nBot must be docked to run the cycle (is {state}). Aborting.")
            return

        print("\n[3] Clean(START):", flush=True)
        await Clean(CleanAction.START).execute(auth, info, bus)  # type: ignore[arg-type]
        await _wait_for(auth, info, bus, {State.CLEANING}, "3 read")

        print("\n[4] Clean(PAUSE):", flush=True)
        await Clean(CleanAction.PAUSE).execute(auth, info, bus)  # type: ignore[arg-type]
        state = await _wait_for(auth, info, bus, {State.PAUSED}, "4 read")
        print(f"  CHECK paused read-back: {state == State.PAUSED}")

        # Home Assistant sends START to resume; the command must swap to apn 40011
        print("\n[5] Clean(START) while paused (expects resume):", flush=True)
        cmd = Clean(CleanAction.START)
        await cmd.execute(auth, info, bus)  # type: ignore[arg-type]
        print(f"  CHECK apn used was 40011: {cmd.apn == 40011}")
        state = await _wait_for(auth, info, bus, {State.CLEANING}, "5 read")
        print(f"  CHECK resumed read-back: {state == State.CLEANING}")

        print("\n[6] Clean(PAUSE) then Charge():", flush=True)
        await Clean(CleanAction.PAUSE).execute(auth, info, bus)  # type: ignore[arg-type]
        await asyncio.sleep(3)
        await Charge().execute(auth, info, bus)  # type: ignore[arg-type]
        state = await _wait_for(auth, info, bus, {State.RETURNING, State.DOCKED}, "6 read")
        print(f"  CHECK returning/docked, not paused: {state in {State.RETURNING, State.DOCKED}}")
        state = await _wait_for(auth, info, bus, {State.DOCKED}, "6 dock")
        print(f"  CHECK docked: {state == State.DOCKED}")

        print("\nCycle complete. Every CHECK line above should read True.")


if __name__ == "__main__":
    asyncio.run(main())
