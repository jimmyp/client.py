"""Experiment 2: probe whether routing commands to the device's ngiot REST
host (instead of the legacy portal) yields real data for q287s6.

Round A sends a few commands to the legacy portal (baseline, expected null).
Round B sends the SAME commands to the device's `service.mqs` (api-ngiot) host.
Raw REST responses are captured for both.

Creds from env: ECOVACS_USERNAME, ECOVACS_PASSWORD, ECOVACS_COUNTRY.
Run: cd /home/user/client.py && uv run --frozen python <this file>
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import time

import aiohttp

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.device import Device
from deebot_client.models import DeviceInfo
from deebot_client.util import md5
from deebot_client.hardware.zg6qbz import get_device_info as json_info

from deebot_client.commands.json.battery import GetBattery
from deebot_client.commands.json.charge_state import GetChargeState
from deebot_client.commands.json.clean import GetCleanInfo
from deebot_client.commands.json.stats import GetStats
from deebot_client.commands.json.work_state import GetWorkState

TARGET = "q287s6"
PROBES = [
    ("GetBattery", GetBattery()),
    ("GetChargeState", GetChargeState()),
    ("GetStats", GetStats()),
    ("GetWorkState", GetWorkState()),
    ("GetCleanInfo", GetCleanInfo()),
]


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    device_id = md5(str(time.time()))

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=device_id, alpha_2_country=country)
        legacy_url = rest.portal_url
        auth = Authenticator(rest, user, md5(pw))
        api = ApiClient(auth)

        devices = await api.get_devices()
        api_info = None
        for d in devices.mqtt:
            if d.api.get("class") == TARGET:
                api_info = d.api
        for d in devices.not_supported:
            if d.get("class") == TARGET:
                api_info = d
        if not api_info:
            print("device not found on account")
            return

        svc = api_info.get("service", {})
        mqs = svc.get("mqs")
        print(f"service block: {svc}")
        print(f"legacy portal: {legacy_url}")
        print(f"ngiot mqs host: {mqs}")

        # Capture raw REST responses going through post_authenticated.
        captured: list = []
        orig = auth.post_authenticated

        async def wrapped(path, json, **kw):  # noqa: ANN001, ANN202
            try:
                resp = await orig(path, json, **kw)
            except Exception as ex:  # noqa: BLE001
                resp = {"<exception>": repr(ex)}
            captured.append(resp)
            return resp

        auth.post_authenticated = wrapped  # type: ignore[method-assign]
        dev = Device(DeviceInfo(api_info, json_info()), auth)

        async def run_round(label: str, base_url: str) -> None:
            auth._auth_client._config = dataclasses.replace(  # noqa: SLF001
                auth._auth_client._config, portal_url=base_url  # noqa: SLF001
            )
            print(f"\n===== ROUND: {label}  ->  {base_url} =====")
            for name, cmd in PROBES:
                captured.clear()
                try:
                    r = await dev.execute_command(cmd)
                except Exception as ex:  # noqa: BLE001
                    r = f"<exc {ex!r}>"
                raw = captured[-1] if captured else None
                print(f"{name}: execute_command={r!r}")
                print(f"    raw REST resp: {raw!r}")
                await asyncio.sleep(1)

        await run_round("legacy portal (baseline)", legacy_url)
        if mqs:
            await run_round("ngiot api host", f"https://{mqs}")
        else:
            print("\nno mqs host in service block -- cannot probe ngiot")


if __name__ == "__main__":
    asyncio.run(main())
