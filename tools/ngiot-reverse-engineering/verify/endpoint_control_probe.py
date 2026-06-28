"""Live ngiot endpoint-control probe for q287s6 -- VERIFIED WORKING transport+auth.

This mints an SST token and calls the ngiot endpoint-control API the way the
official app's next-gen transport does (see DeebotUniverse/client.py PR #1569).
Against a real DEEBOT NEO 2.0 PLUS (q287s6) this returns HTTP 200 / code:0 /
msg:"ok" -- i.e. the transport and auth are correct.

WHAT WORKS (verified live 2026-06-28):
- SST issue at api-base.dc-<region>.ww.ecouser.net/api/new-perm/token/sst/issue
- endpoint/control at the service.mqs host (api-ngiot.dc-<region>.ww.ecouser.net).
  NOTE: the api-base host returns 404 for control in NA; use the mqs host.

WHAT'S STILL UNKNOWN:
- The per-command `apn` + body.data shapes that return real telemetry. Sending
  the command names as apn just echoes the request body. Those surface IDs must
  be captured from the official app's traffic (blocked by Android-7 user-CA on a
  non-rooted phone -- needs Frida SSL-unpinning or an emulator system CA).

Run (creds from env, e.g. sourced from ~/.ecovacs.env):
    python tools/ngiot-reverse-engineering/verify/endpoint_control_probe.py [apn] [json_body_data]
e.g.
    python tools/ngiot-reverse-engineering/verify/endpoint_control_probe.py getBattery '{"type":["all"]}'
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


def _base_from_mqs(mqs: str) -> str:
    # api-ngiot.dc-na.ww.ecouser.net -> https://api-base.dc-na.ww.ecouser.net
    if mqs.startswith("api-ngiot."):
        return "https://api-base." + mqs.split(".", 1)[1]
    return "https://" + mqs


async def _mint_sst(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    user_id: str,
    cls: str,
    did: str,
) -> str:
    url = base + "/api/new-perm/token/sst/issue"
    payload = {
        "acl": [
            {
                "policy": [{"obj": [f"Endpoint:{cls}:{did}"], "perms": ["Control"]}],
                "svc": "dim",
            }
        ],
        "exp": 600,
        "sub": user_id,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    async with session.post(url, json=payload, headers=headers) as res:
        res.raise_for_status()
        body = orjson.loads(await res.read())
    return body["data"]["data"]["token"]


async def _control(
    session: aiohttp.ClientSession,
    host: str,
    sst: str,
    did: str,
    cls: str,
    res: str,
    apn: str,
    body_data: dict,
) -> tuple[int, object]:
    url = f"https://{host}/api/iot/endpoint/control"
    si = secrets.token_hex(16)
    payload = {
        "body": {"data": body_data},
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
        "eid": did,
        "et": cls,
        "er": res,
        "apn": apn,
        "fmt": "j",
    }
    headers = {
        "Authorization": f"Bearer {sst}",
        "x-eco-request-id": si,
        "Content-Type": "application/octet-stream",
        "User-Agent": "okhttp/4.9.1",
    }
    async with session.post(
        url, params=params, data=orjson.dumps(payload), headers=headers
    ) as r:
        raw = await r.read()
        try:
            return r.status, orjson.loads(raw)
        except Exception:
            return r.status, raw.decode("utf-8", "replace")


async def main() -> None:
    apn = sys.argv[1] if len(sys.argv) > 1 else "getInfo"
    body_data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    user = os.environ["ECOVACS_USERNAME"]
    pw = os.environ["ECOVACS_PASSWORD"]
    country = os.environ.get("ECOVACS_COUNTRY", "AU")
    did_local = md5(str(time.time()))

    async with aiohttp.ClientSession() as session:
        rest = create_rest_config(session, device_id=did_local, alpha_2_country=country)
        auth = Authenticator(rest, user, md5(pw))
        api = ApiClient(auth)
        devices = await api.get_devices()
        info = next(d for d in devices.not_supported if d.get("class") == TARGET)
        did, cls, res = info["did"], info["class"], info["resource"]
        mqs = info["service"]["mqs"]
        base = _base_from_mqs(mqs)

        creds = await auth.authenticate()
        sst = await _mint_sst(session, base, creds.token, creds.user_id, cls, did)
        print(f"SST minted ({len(sst)} chars)", flush=True)

        status, resp = await _control(session, mqs, sst, did, cls, res, apn, body_data)
        print(f"apn={apn} -> HTTP {status}", flush=True)
        print(
            json.dumps(resp, indent=2) if isinstance(resp, dict) else resp, flush=True
        )


if __name__ == "__main__":
    asyncio.run(main())
