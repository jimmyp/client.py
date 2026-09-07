"""Wildcard MQTT capture for DEEBOT NEO 2.0 PLUS (q287s6) -- RUN LOCALLY.

Unlike the deebot_client default (which only subscribes to three narrow,
JSON-pinned per-device topics), this subscribes to EVERYTHING the broker will
give us (`iot/#` and `#`) so we don't miss ngiot pushes on an unexpected
topic shape. It uses deebot-client only to log in and obtain broker
credentials, then talks to MQTT directly via aiomqtt.

Must run on a network that allows MQTT to Ecovacs (e.g. your Home Assistant
host). The sandbox can't -- its egress is HTTPS-only.

Setup:  pip install deebot-client aiomqtt aiohttp
Run:
    ECOVACS_USERNAME='email-or-phone' ECOVACS_PASSWORD='password' \
    ECOVACS_COUNTRY='AU' CAPTURE_SECS=180 python ngiot_capture_wild.py

When it prints "CAPTURING", open the official app and start cleaning, pause,
and send the vacuum to the dock. Then paste capture_q287s6.txt.
(The file contains your device id/name -- review before sharing.)
"""

from __future__ import annotations

import asyncio
import os
import ssl
import time

import aiohttp
import aiomqtt

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.util import md5

TARGET = "q287s6"
DURATION = int(os.environ.get("CAPTURE_SECS", "180"))
# Try the broadest first; `#` is the total backstop.
TOPICS = ["iot/#", "#"]


async def main() -> None:
    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    device_id = md5(str(time.time()))

    lines: list[str] = []

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=device_id, alpha_2_country=country)
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

        jmq = api_info.get("service", {}).get("jmq")
        print(f"device: {api_info.get('did')}  broker: {jmq}", flush=True)
        lines.append(f"device service block: {api_info.get('service', {})}")

        creds = await auth.authenticate()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        client = aiomqtt.Client(
            hostname=jmq,
            port=443,
            username=creds.user_id,
            password=creds.token,
            identifier=f"{creds.user_id}@ecouser/{device_id}",
            tls_context=ctx,
        )

        try:
            async with client:
                for t in TOPICS:
                    try:
                        await client.subscribe(t)
                        print(f"subscribed: {t}", flush=True)
                    except Exception as ex:  # noqa: BLE001
                        print(f"subscribe {t} failed: {ex!r}", flush=True)

                print(f"CAPTURING for {DURATION}s -- DRIVE THE VACUUM NOW.", flush=True)

                async def pump() -> None:
                    async for m in client.messages:
                        line = (
                            f"{time.strftime('%H:%M:%S')}  {m.topic.value}\n"
                            f"    {m.payload!r}"
                        )
                        print(line, flush=True)
                        lines.append(line)

                try:
                    await asyncio.wait_for(pump(), timeout=DURATION)
                except asyncio.TimeoutError:
                    pass
        except Exception as ex:  # noqa: BLE001
            print(f"MQTT connection failed: {ex!r}", flush=True)
            lines.append(f"MQTT connection failed: {ex!r}")

    with open("capture_q287s6.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    msg_count = sum(1 for line in lines if line.startswith(tuple("0123456789")))
    print(f"\ncaptured {msg_count} message(s) -> capture_q287s6.txt", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
