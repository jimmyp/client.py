# Reverse-engineering an Ecovacs ngiot device

This is the toolkit and the paper trail for working out how a next-gen Ecovacs
"ngiot" (`eco-ng`) device actually talks, so it can be supported in
deebot-client. It was written while adding the **DEEBOT NEO 2.0 PLUS (`q287s6`)**
— the first ngiot device in the library — but the method is general: any
`eco-ng` device with a `service.mqs` host of `api-ngiot.dc-<region>.ww.ecouser.net`
speaks the same protocol shape.

## Why this exists

ngiot devices authenticate fine and then create no entities, because they don't
answer the legacy `iot/devmanager.do` portal endpoint deebot-client has always
used — every command comes back `code:0, data:null`. They use a different
transport entirely: a short-lived per-device **SST** token, then a POST to
`endpoint/control` addressing **numeric `apn` surface ids** (not command names).
None of that is documented anywhere; the only source of truth is the official
app's own traffic. So we capture it.

For the full transport/auth write-up see [`findings/PROTOCOL.md`](findings/PROTOCOL.md);
this README is the walkthrough of how to get there for a new device.

## The journey, in three stages

```
capture  ──▶  verify  ──▶  implement
(what does     (can WE drive    (turn it into deebot-client
 the app send?) it the same way?) ngiot commands + a profile)
```

### Stage 1 — capture (`capture/`)

You cannot guess the `apn` surfaces; you have to watch the official app. There
are two angles, and you'll likely need both.

- **REST routing probe** — [`capture/01_rest_routing_probe.py`](capture/01_rest_routing_probe.py).
  Sends the same commands to the legacy portal and to the device's `api-ngiot`
  host. This is what proves the legacy path is a dead end (`data:null`) and
  points you at ngiot. Start here to confirm you're dealing with an ngiot device.
- **MQTT wildcard capture** — [`capture/02_mqtt_wildcard_capture.py`](capture/02_mqtt_wildcard_capture.py)
  (timer-based) and [`capture/03_mqtt_live_capture.py`](capture/03_mqtt_live_capture.py)
  (manual-stop, streams to disk). These subscribe to `iot/#`/`#` on the device's
  broker. Useful to learn topic shapes, but be warned: on q287s6 the ngiot
  broker is ACL-scoped and **passive eavesdropping returns nothing** — which is
  itself a finding that pushes you to the app capture below.
- **App traffic capture** — [`capture/mitmproxy_addon.py`](capture/mitmproxy_addon.py).
  The real prize. A mitmproxy addon that logs every `endpoint/control` call (and
  SST issue) the app makes, to `ngiot_app_capture.jsonl`. Getting the app's TLS
  to go through mitmproxy on a modern Android app needs an emulator with the CA
  in the **system** store plus Frida SSL-unpinning — the full rig recipe (every
  gotcha, including the H5/WebView UI and the attach-not-spawn quirk) is in
  [`findings/FINDINGS.md`](findings/FINDINGS.md).

### Stage 2 — verify (`verify/`)

Capturing what the app sends isn't the same as proving *you* can send it. The
device returns `code:0` for some no-op/unknown payloads, so "accepted" ≠
"correct" — you have to watch real state change.

- **Raw transport probe** — [`verify/endpoint_control_probe.py`](verify/endpoint_control_probe.py).
  Mints an SST and fires a single `endpoint/control` call at an `apn` you give
  it. This is how you confirm the transport + auth work before touching the
  library, and how you brute-check a captured payload.
- **End-to-end against the command classes** — [`verify/q287s6_live_e2e.py`](verify/q287s6_live_e2e.py).
  Drives the *actual* deebot-client ngiot command classes against the real
  device: reads state, optionally (`--control`) issues a benign write and reads
  it back. This is the live evidence that the implementation works, not just the
  wire shape.

### Stage 3 — implement

Once a surface is captured **and** verified, it becomes a real ngiot command in
`deebot_client/commands/ngiot/` and gets wired into the hardware profile, with a
wire-contract test pinning the exact payload. That work lives in the main
library, not here; this folder is the evidence it's based on.

## What you need

- Python with `uv` (the repo's toolchain), plus `aiohttp`/`aiomqtt`/`orjson`.
- A real device on your Ecovacs account, online.
- Credentials in `~/.ecovacs.env` (gitignored), sourced before running:
  ```bash
  export ECOVACS_USERNAME="email-or-phone"
  export ECOVACS_PASSWORD="password"
  export ECOVACS_COUNTRY="AU"     # ISO alpha-2 of the account
  ```
- For the app capture: an Android emulator + mitmproxy + Frida. See
  [`findings/FINDINGS.md`](findings/FINDINGS.md) for the full bring-up recipe.

## A warning about secrets

The capture outputs (`capture_q287s6.txt`, `ngiot_app_capture.jsonl`) contain
your device id, IP and MAC. They're gitignored on purpose. The committed
`findings/` docs have those values redacted — keep it that way if you add to them.

## Findings

- [`findings/PROTOCOL.md`](findings/PROTOCOL.md) — the captured ngiot protocol:
  transport, SST auth, and the full `apn` surface catalog for q287s6.
- [`findings/FINDINGS.md`](findings/FINDINGS.md) — the investigation narrative
  plus the emulator/Frida/mitmproxy rig bring-up recipe.
- [`findings/TEST_REPORT.md`](findings/TEST_REPORT.md) — the live manual-test
  report and what automated tests can vs. can't cover.

Refs: DeebotUniverse/client.py#1569 (the ngiot transport groundwork) and
DeebotUniverse/client.py#1642 (the q287s6 support request).
