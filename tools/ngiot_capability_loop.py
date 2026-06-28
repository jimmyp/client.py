"""ngiot capability feedback-loop harness for q287s6 (headless, no app/MITM).

apn=10001 is a unified field-query oracle. Discover + VERIFY surfaces autonomously:
  - READ: ask 10001 for candidate fields; a non-null value = confirmed read surface.
  - WRITE: set (apn,payload), read the affected field via 10001, diff. code:0 alone
    is ignored; only an observable state change confirms a real control surface.

Authenticates + mints SST ONCE, then reuses it across all probes (fast sweeps).

Usage:
  python ngiot_loop.py fields
  python ngiot_loop.py read  <f1,f2,...>
  python ngiot_loop.py sweep <field> <jsonvalue> <apn_start> <apn_end> [step]
       e.g. sweep volume 3 50001 50031 2     # set {field:val} on each apn, diff field
  python ngiot_loop.py setcheck <apn> <jsonpayload> <readfield>
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time

import aiohttp
import orjson

from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.util import md5

TARGET = "q287s6"


class Loop:
    def __init__(self, session, mqs, sst, did, cls, res):
        self.s, self.mqs, self.sst = session, mqs, sst
        self.did, self.cls, self.res = did, cls, res

    async def control(self, apn, data):
        url = f"https://{self.mqs}/api/iot/endpoint/control"
        si = secrets.token_hex(16)
        payload = {
            "body": {"data": data},
            "header": {
                "channel": "Android",
                "m": "request",
                "pri": 2,
                "reqid": secrets.token_hex(3),
                "ts": str(int(time.time() * 1000)),
                "tzc": "UTC",
                "tzm": 0,
                "ver": "0.0.22",
            },
        }
        params = {
            "si": si,
            "ct": "q",
            "eid": self.did,
            "et": self.cls,
            "er": self.res,
            "apn": str(apn),
            "fmt": "j",
        }
        headers = {
            "Authorization": f"Bearer {self.sst}",
            "x-eco-request-id": si,
            "Content-Type": "application/octet-stream",
            "User-Agent": "okhttp/4.9.1",
        }
        async with self.s.post(
            url, params=params, data=orjson.dumps(payload), headers=headers
        ) as r:
            raw = await r.read()
            try:
                return orjson.loads(raw).get("body", {})
            except Exception:
                return {"_raw": raw.decode("utf-8", "replace")[:200]}

    async def read(self, fields):
        return (await self.control(10001, {"fields": fields})).get("data", {})


async def build(session) -> Loop:
    user, pw = os.environ["ECOVACS_USERNAME"], os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    rest = create_rest_config(
        session, device_id=md5(str(time.time())), alpha_2_country=country
    )
    auth = Authenticator(rest, user, md5(pw))
    api = ApiClient(auth)
    devices = await api.get_devices()
    info = None
    for d in devices.mqtt:
        if d.api.get("class") == TARGET:
            info = d.api
    for d in devices.not_supported:
        if d.get("class") == TARGET:
            info = d
    if info is None:
        raise RuntimeError("q287s6 not found")
    did, cls, res = info["did"], info["class"], info["resource"]
    mqs = info["service"]["mqs"]
    base = "https://api-base." + mqs.split(".", 1)[1]
    creds = await auth.authenticate()
    async with session.post(
        base + "/api/new-perm/token/sst/issue",
        json={
            "acl": [
                {
                    "policy": [
                        {"obj": [f"Endpoint:{cls}:{did}"], "perms": ["Control"]}
                    ],
                    "svc": "dim",
                }
            ],
            "exp": 600,
            "sub": creds.user_id,
        },
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    ) as r:
        sst = orjson.loads(await r.read())["data"]["data"]["token"]
    return Loop(session, mqs, sst, did, cls, res)


CANDIDATE_FIELDS = [
    "battery",
    "chargeStatus",
    "stationStatus",
    "stationType",
    "fanMode",
    "waterMode",
    "workMode",
    "mopState",
    "pauseSwitch",
    "status",
    "error",
    "consumables",
    "cleanCount",
    "cleanArea",
    "cleanTime",
    "volume",
    "trueDetect",
    "autoEmpty",
    "carpetPressure",
    "aiavoid",
    "borderSpin",
    "continuousClean",
    "sweepMode",
    "speaker",
    "sound",
    "voiceReport",
    "advancedMode",
    "mopAutoWash",
    "dryingDuration",
    "stationInfo",
    "childLock",
    "trueDetectAvoid",
]


async def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fields"
    async with aiohttp.ClientSession() as s:
        loop = await build(s)

        if cmd == "fields":
            data = await loop.read(CANDIDATE_FIELDS)
            nonnull = {k: v for k, v in data.items() if v is not None}
            nullk = sorted(k for k, v in data.items() if v is None)
            print(f"NON-NULL (confirmed reads): {json.dumps(nonnull)[:600]}")
            print(f"NULL (known but not reporting now): {nullk}")
        elif cmd == "read":
            print(json.dumps(await loop.read(sys.argv[2].split(",")), indent=1))
        elif cmd == "setcheck":
            apn, payload, field = int(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4]
            before = (await loop.read([field])).get(field)
            code = (await loop.control(apn, payload)).get("code")
            await asyncio.sleep(2)
            after = (await loop.read([field])).get(field)
            print(
                f"apn={apn} {payload} {field}: code={code} | {before!r}->{after!r} | "
                f"{'REAL' if before != after else 'no-change'}"
            )
        elif cmd == "sweep":
            field, val = sys.argv[2], json.loads(sys.argv[3])
            start, end = int(sys.argv[4]), int(sys.argv[5])
            step = int(sys.argv[6]) if len(sys.argv) > 6 else 2
            before = (await loop.read([field])).get(field)
            print(
                f"baseline {field}={before!r}; sweeping {start}..{end} step {step} with {{{field}:{val}}}"
            )
            for apn in range(start, end + 1, step):
                code = (await loop.control(apn, {field: val})).get("code")
                await asyncio.sleep(1.2)
                after = (await loop.read([field])).get(field)
                tag = (
                    "  <<< REAL SET SURFACE" if after == val and before != after else ""
                )
                if code == 0 or tag:
                    print(
                        f"  apn={apn}: code={code} {field} {before!r}->{after!r}{tag}",
                        flush=True,
                    )
                if tag:  # restore + stop on first hit
                    await loop.control(apn, {field: before})
                    break


if __name__ == "__main__":
    asyncio.run(main())
