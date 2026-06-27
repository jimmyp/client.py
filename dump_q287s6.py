"""Diagnostic dump for the DEEBOT NEO 2.0 PLUS (class q287s6).

Talks directly to the Ecovacs cloud + MQTT (independent of Home Assistant),
so it works even though the device shows no entities in HA.

It does three things:
  1. Lists every device on your account (and whether deebot_client recognises
     each class).
  2. Prints the cloud's authoritative "product IoT map" entry for your
     device's class -- i.e. exactly which commands Ecovacs says the device
     supports.
  3. Forces a batch of JSON commands at the device and prints the RAW reply
     for each one, so we can see which return real data vs `data: None`.

Everything is also written to `dump_q287s6.txt`.

Credentials are read from environment variables; nothing is hardcoded and the
password is md5-hashed locally before use and never printed:
    ECOVACS_USERNAME, ECOVACS_PASSWORD, ECOVACS_COUNTRY (2-letter, e.g. AU)

Run (from the repo root):
    uv run --frozen python dump_q287s6.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import aiohttp

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.device import Device
from deebot_client.models import DeviceInfo
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5

# A known-good JSON profile, used only so a Device can be constructed for the
# (currently unsupported) q287s6. We send commands explicitly below, so the
# profile's own capability list does not matter -- we just need JSON transport.
from deebot_client.hardware.zg6qbz import get_device_info as _json_device_info

# JSON commands we want to probe. Each is sent and its raw response printed.
from deebot_client.commands.json.battery import GetBattery
from deebot_client.commands.json.charge_state import GetChargeState
from deebot_client.commands.json.clean import GetCleanInfo, GetCleanInfoV2
from deebot_client.commands.json.clean_logs import GetCleanLogs
from deebot_client.commands.json.error import GetError
from deebot_client.commands.json.fan_speed import GetFanSpeed
from deebot_client.commands.json.life_span import GetLifeSpan
from deebot_client.commands.json.map import (
    GetCachedMapInfo,
    GetMajorMap,
    GetMapTrace,
)
from deebot_client.commands.json.network import GetNetInfo
from deebot_client.commands.json.pos import GetPos
from deebot_client.commands.json.stats import GetStats, GetTotalStats
from deebot_client.commands.json.water_info import GetWaterInfo
from deebot_client.commands.json.work_state import GetWorkState
from deebot_client.events import LifeSpan

TARGET_CLASS = "q287s6"

PROBE_COMMANDS = [
    ("GetBattery", GetBattery()),
    ("GetChargeState", GetChargeState()),
    ("GetWorkState", GetWorkState()),
    ("GetCleanInfo", GetCleanInfo()),
    ("GetCleanInfoV2", GetCleanInfoV2()),
    ("GetStats", GetStats()),
    ("GetTotalStats", GetTotalStats()),
    ("GetError", GetError()),
    ("GetFanSpeed", GetFanSpeed()),
    ("GetWaterInfo", GetWaterInfo()),
    (
        "GetLifeSpan",
        GetLifeSpan([LifeSpan.BRUSH, LifeSpan.FILTER, LifeSpan.SIDE_BRUSH]),
    ),
    ("GetCachedMapInfo", GetCachedMapInfo()),
    ("GetMajorMap", GetMajorMap()),
    ("GetMapTrace", GetMapTrace()),
    ("GetPos", GetPos()),
    ("GetNetInfo", GetNetInfo()),
    ("GetCleanLogs", GetCleanLogs()),
]

_OUT_LINES: list[str] = []


def out(line: str = "") -> None:
    """Print and record a line."""
    print(line)
    _OUT_LINES.append(line)


async def main() -> None:
    """Run the dump."""
    logging.basicConfig(level=logging.DEBUG)

    username = os.environ["ECOVACS_USERNAME"]
    password = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    device_id = md5(str(time.time()))

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=device_id, alpha_2_country=country)
        authenticator = Authenticator(rest, username, md5(password))
        api_client = ApiClient(authenticator)

        out("=" * 70)
        out("1) DEVICES ON ACCOUNT")
        out("=" * 70)
        devices = await api_client.get_devices()
        out(f"recognised (mqtt): {[d.api.get('class') for d in devices.mqtt]}")
        out(f"NOT recognised   : {[d.get('class') for d in devices.not_supported]}")
        out(f"legacy (xmpp)    : {[d.get('class') for d in devices.xmpp]}")

        # Locate the target device's raw api info in either list.
        api_info: dict[str, Any] | None = None
        for d in devices.mqtt:
            if d.api.get("class") == TARGET_CLASS:
                api_info = d.api
        for d in devices.not_supported:
            if d.get("class") == TARGET_CLASS:
                api_info = d
        out()
        out(f"target {TARGET_CLASS} api info:")
        out(repr(api_info))

        out()
        out("=" * 70)
        out("2) CLOUD IOT MAP (authoritative supported-command list)")
        out("=" * 70)
        try:
            iot_map = await api_client.get_product_iot_map()
            out(repr(iot_map.get(TARGET_CLASS, "NOT FOUND in iot map")))
        except Exception as ex:  # noqa: BLE001
            out(f"failed to get iot map: {ex!r}")

        if api_info is None:
            out()
            out(f"!! {TARGET_CLASS} not found on this account -- check country/login.")
            _save()
            return

        out()
        out("=" * 70)
        out("3) RAW COMMAND RESPONSES (JSON transport)")
        out("=" * 70)
        device = Device(DeviceInfo(api_info, _json_device_info()), authenticator)
        mqtt = MqttClient(
            create_mqtt_config(device_id=device_id, country=country), authenticator
        )
        await device.initialize(mqtt)
        try:
            for name, command in PROBE_COMMANDS:
                try:
                    response = await device.execute_command(command)
                except Exception as ex:  # noqa: BLE001
                    response = f"<exception: {ex!r}>"
                out(f"\n--- {name} ---")
                out(repr(response))
                await asyncio.sleep(1)
        finally:
            await device.teardown()
            await mqtt.disconnect()

    _save()


def _save() -> None:
    with open("dump_q287s6.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(_OUT_LINES))
    print("\nSaved to dump_q287s6.txt")


if __name__ == "__main__":
    asyncio.run(main())
