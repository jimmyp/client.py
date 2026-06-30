"""Live wildcard MQTT capture for q287s6 -- manual stop, streams to disk.

Same auth/connection path as ngiot_capture_wild.py, but:
- appends each message to capture_q287s6.txt as it arrives (flushed), so
  nothing is lost if the run is interrupted; and
- runs until the process is stopped (no wall-clock timer), so you can drive
  the vacuum at your own pace.

Run (creds come from the environment, e.g. sourced from ~/.ecovacs.env):
    python tools/ngiot_capture_live.py

Stop it (from another shell, or have the caller kill it) once you've
exercised the vacuum: start a clean, pause, resume, send to dock.
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
OUTFILE = "capture_q287s6.txt"
TOPICS = ["iot/#", "#"]


async def main() -> None:
    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    device_id = md5(str(time.time()))

    out = open(OUTFILE, "w", encoding="utf-8")  # noqa: SIM115

    def emit(line: str) -> None:
        print(line, flush=True)
        out.write(line + "\n")
        out.flush()

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
            emit("device not found on account")
            out.close()
            return

        jmq = api_info.get("service", {}).get("jmq")
        emit(f"device service block: {api_info.get('service', {})}")
        print(f"device: {api_info.get('did')}  broker: {jmq}", flush=True)

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

        msg_count = 0
        try:
            async with client:
                for t in TOPICS:
                    try:
                        await client.subscribe(t)
                        print(f"subscribed: {t}", flush=True)
                    except Exception as ex:  # noqa: BLE001
                        print(f"subscribe {t} failed: {ex!r}", flush=True)

                print(
                    "CAPTURING (no timer) -- DRIVE THE VACUUM NOW. Stop me when done.",
                    flush=True,
                )

                async for m in client.messages:
                    msg_count += 1
                    emit(
                        f"{time.strftime('%H:%M:%S')}  {m.topic.value}\n"
                        f"    {m.payload!r}"
                    )
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except Exception as ex:  # noqa: BLE001
            emit(f"MQTT connection failed: {ex!r}")
        finally:
            print(f"\ncaptured {msg_count} message(s) -> {OUTFILE}", flush=True)
            out.close()


if __name__ == "__main__":
    asyncio.run(main())
