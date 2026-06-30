"""Live manual test for adaptive state polling (PR #4) on a real q287s6.

Builds a REAL ``Device(state_refresh=True)`` against the live cloud and runs its
actual ``_state_refresh_worker``. MQTT presence is stubbed with a no-op client
(the refresh loop drives ``GetState`` over the ngiot REST path, not MQTT), so the
loop, the interval selection and the back-off are all the real code under test.

It logs every state-refresh poll with a wall-clock delta so you can SEE the
cadence change: ~fast while the bot is active, ~slow when docked.

By default it sends ``Clean`` (start) then, after observing the fast cadence,
``Charge`` (dock) to exercise both intervals. THIS MOVES THE VACUUM.
Pass ``--read-only`` to just watch the current state's cadence with no motion.

Intervals are patched DOWN (active=5s, idle=20s) so the demo is quick; the
production defaults are 10s/60s. Credentials from the environment:
    source ~/.ecovacs.env   # ECOVACS_USERNAME, ECOVACS_PASSWORD, ECOVACS_COUNTRY

Run:
    uv run --frozen python tools/adaptive_polling_live.py            # start + dock
    uv run --frozen python tools/adaptive_polling_live.py --read-only
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import os
import sys
import time
from typing import Any
from unittest.mock import patch

import aiohttp

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
import deebot_client.device as device_mod
from deebot_client.device import Device
from deebot_client.events import StateEvent
from deebot_client.util import md5

TARGET = "q287s6"
# Shrunk for a quick demo (prod defaults are 10s / 60s).
ACTIVE = 5
IDLE = 20


class _NoopMqtt:
    """Stand-in MqttClient: the refresh loop never needs real MQTT presence."""

    async def subscribe(self, *_: Any, **__: Any) -> Any:
        return lambda: None


def _log(msg: str) -> None:
    print(f"{datetime.now(tz=UTC):%H:%M:%S} | {msg}", flush=True)


async def main() -> None:
    read_only = "--read-only" in sys.argv[1:]

    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    device_id = md5(str(time.time()))

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=device_id, alpha_2_country=country)
        auth = Authenticator(rest, user, md5(pw))
        api = ApiClient(auth)

        devices = await api.get_devices()
        device = next((d for d in devices.mqtt if d.api.get("class") == TARGET), None)
        if device is None:
            _log(f"No {TARGET} found; supported: {[d.api.get('class') for d in devices.mqtt]}")
            return
        _log(f"Found {TARGET} did={device.api['did']}")

        # Real Device with the opt-in ON. Patch the module intervals so the demo
        # is quick but it's the real worker doing the work.
        with (
            patch.object(device_mod, "_STATE_REFRESH_INTERVAL_ACTIVE", ACTIVE),
            patch.object(device_mod, "_STATE_REFRESH_INTERVAL_IDLE", IDLE),
        ):
            bot = Device(device, auth, state_refresh=True)

            # Observe each poll: log the state + seconds since the previous poll.
            last_poll: dict[str, float] = {}

            async def on_state(event: StateEvent) -> None:
                now = time.monotonic()
                delta = now - last_poll.get("t", now)
                last_poll["t"] = now
                interval = bot._state_refresh_interval()  # noqa: SLF001
                _log(
                    f"  poll -> state={event.state.name:9s} "
                    f"(+{delta:4.1f}s)  next interval={interval}s"
                )

            bot.events.subscribe(StateEvent, on_state)
            await bot.initialize(_NoopMqtt())  # type: ignore[arg-type]
            _log(f"state-refresh loop started (active={ACTIVE}s idle={IDLE}s)")

            try:
                if read_only:
                    _log("read-only: watching current cadence for 30s ...")
                    await asyncio.sleep(30)
                    return

                # --- exercise the ACTIVE cadence ---
                _log(">>> sending Clean (START) -- bot will move")
                await bot.execute_command(_clean())
                _log("watching FAST cadence for ~18s (expect polls ~every 5s) ...")
                await asyncio.sleep(18)

                # --- exercise the IDLE cadence ---
                _log(">>> sending Charge (DOCK)")
                await bot.execute_command(_charge())
                _log("watching SLOW cadence for ~45s (expect polls ~every 20s) ...")
                await asyncio.sleep(45)
            finally:
                await bot.teardown()
                _log("torn down.")


def _clean() -> Any:
    from deebot_client.commands.ngiot.clean import Clean
    from deebot_client.models import CleanAction

    return Clean(CleanAction.START)


def _charge() -> Any:
    from deebot_client.commands.ngiot.clean import Charge

    return Charge()


if __name__ == "__main__":
    asyncio.run(main())
