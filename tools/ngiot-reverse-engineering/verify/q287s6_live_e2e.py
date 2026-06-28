"""Live end-to-end check for q287s6 using the new ngiot command classes.

Unlike ``verify/endpoint_control_probe.py`` (which proved the raw transport), this script
drives the actual library command classes added for the DEEBOT NEO 2.0 PLUS:

1. Authenticate, then locate the q287s6 device (now recognised, so it appears in
   ``devices.mqtt``).
2. Execute ``GetState`` (apn 10001) and print every event it emits -- battery,
   state, fan, water, mop, error and life-span.
3. Optionally (``--control``) issue a deliberately benign write: re-apply the
   *current* fan mode (a no-op change) via ``SetFanSpeed``, then read state back.

Credentials come from the environment (e.g. ``source ~/.ecovacs.env``):
    ECOVACS_USERNAME, ECOVACS_PASSWORD, ECOVACS_COUNTRY

Run:
    python tools/ngiot-reverse-engineering/verify/q287s6_live_e2e.py            # read-only
    python tools/ngiot-reverse-engineering/verify/q287s6_live_e2e.py --control  # + benign fan re-apply

TLS note: this uses the library's normal aiohttp session with full certificate
verification. It never disables TLS checks.
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
from deebot_client.commands.ngiot.settings import SetFanSpeed
from deebot_client.commands.ngiot.state import GetState
from deebot_client.events import FanSpeedEvent
from deebot_client.events.base import Event
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


async def main() -> None:
    control = "--control" in sys.argv[1:]

    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    device_id = md5(str(time.time()))

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=device_id, alpha_2_country=country)
        auth = Authenticator(rest, user, md5(pw))
        api = ApiClient(auth)

        devices = await api.get_devices()
        device = next(
            (d for d in devices.mqtt if d.api.get("class") == TARGET), None
        )
        if device is None:
            print(f"No {TARGET} found among supported devices.", flush=True)
            classes = [d.api.get("class") for d in devices.mqtt]
            print(f"Supported devices: {classes}", flush=True)
            return

        info = device.api
        print(f"Found {TARGET} did={info['did']}", flush=True)

        print("\n[1] GetState:", flush=True)
        recorder = _Recorder()
        await GetState().execute(auth, info, recorder)  # type: ignore[arg-type]

        if not control:
            print("\nRead-only run complete (pass --control to test a write).")
            return

        fan_event = recorder.get_last_event(FanSpeedEvent)
        if not isinstance(fan_event, FanSpeedEvent):
            print("\nNo fan mode reported; skipping benign write.", flush=True)
            return

        # Re-apply the SAME fan mode: a write that does not change device state.
        print(f"\n[2] SetFanSpeed (benign re-apply {fan_event.speed.name}):", flush=True)
        await SetFanSpeed(fan_event.speed).execute(auth, info, _Recorder())  # type: ignore[arg-type]

        print("\n[3] GetState (read back):", flush=True)
        await GetState().execute(auth, info, _Recorder())  # type: ignore[arg-type]


if __name__ == "__main__":
    asyncio.run(main())
