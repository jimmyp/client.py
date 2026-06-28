---
name: capturing-ecovacs-ngiot-protocol
description: Use when a newer Ecovacs / Deebot device (an "ngiot" / eco-ng device) authenticates but returns code:0/data:null to every command, and you need to discover its real cloud protocol to support it in deebot-client.
---

# Capturing the Ecovacs ngiot protocol

## Overview

Next-gen Ecovacs devices (company `eco-ng`, service host
`api-ngiot.dc-<region>.ww.ecouser.net`) do **not** use the legacy transport.
The symptom: the device logs in and lists fine, but every command to the legacy
`iot/devmanager.do` portal returns `code:0, data:null` — the portal accepts the
envelope and answers with nothing, because this device isn't on that transport.

**Core protocol (verified live on q287s6 / DEEBOT NEO 2.0 PLUS):**

1. Mint a short-lived per-device **SST** token.
2. POST to `endpoint/control` addressing a **numeric `apn` surface id** (NOT a
   command name). Reads send `body.data = {"fields": [...]}`; writes send
   `body.data = {"key": value}`.

## STOP — it is NOT MQTT, and NOT command-name-addressed

The single most common wrong turn: assuming it's the legacy model — MQTT on
port 8883, topic-addressed commands (`iot/p2p/...`), or command names like
`getBattery`. **None of that drives an ngiot device.** Specifically:

- **Passive MQTT capture returns nothing.** The ngiot broker is ACL-scoped; you
  can subscribe to `#` and watch the app drive the vacuum and see zero traffic.
  Don't conclude "the device is silent" — conclude "wrong transport."
- **`apn` is a NUMBER, not a name.** Sending `apn=getBattery` just echoes your
  request body back. The real surfaces are ids like `10001`, `40008`, `50011`.
- **The control host is the `service.mqs` host, not `api-base`.** SST issue uses
  `api-base.dc-<region>...`; `endpoint/control` on `api-base` 404s (in NA at
  least) — it must go to `api-ngiot.dc-<region>...`.

If you find yourself writing a paho-mqtt client, you've taken the wrong turn.

## The transport (copy this shape)

**1. Mint SST** (HTTPS, full TLS verification — no `CERT_NONE`):
```
POST https://api-base.dc-<region>.ww.ecouser.net/api/new-perm/token/sst/issue
Authorization: Bearer <account token>
Content-Type: application/json
{"acl":[{"policy":[{"obj":["Endpoint:<class>:<did>"],"perms":["Control"]}],
  "svc":"dim"}],"exp":600,"sub":<user_id>}
-> {"data":{"data":{"token":"SST.<jwt>..."}}}
```

**2. endpoint/control** (octet-stream JSON, returns `code:0`/`msg:ok`):
```
POST https://api-ngiot.dc-<region>.ww.ecouser.net/api/iot/endpoint/control
  query: si=<hex16> ct=q eid=<did> et=<class> er=<resource> apn=<NUMERIC> fmt=j
  headers: Authorization: Bearer <SST>; x-eco-request-id=<si>;
           Content-Type application/octet-stream; User-Agent okhttp/4.9.1
  body: {"body":{"data":{...}},"header":{"channel":"Android","m":"request",
         "pri":2,"reqid":<6hex>,"ts":"<ms>","tzc":"UTC","tzm":0,"ver":"0.0.22"}}
```

A ready probe of exactly this is in
`tools/ngiot-reverse-engineering/verify/endpoint_control_probe.py`.

## You cannot guess the apn catalog — capture it from the app

The numeric `apn` ids and their `body.data` shapes are the firmware's private
vocabulary. The only source of truth is the official app's own traffic. So:

1. MITM the official Ecovacs app's HTTPS — see the
   **REQUIRED SUB-SKILL: frida-mitm-pinned-android-app** (a modern Android app
   pins certs; you need an emulator system CA + Frida unpinning).
2. Log its `endpoint/control` calls with the mitmproxy addon
   `tools/ngiot-reverse-engineering/capture/mitmproxy_addon.py`.
3. Drive every action in the app (start/pause/resume/dock, each fan and water
   level, locate, a consumable reset). Each tap emits one `endpoint/control`
   call — read off the `apn` + `body.data`.

## Verify before you believe it

`code:0` does **not** mean the command worked — the device returns `code:0` for
some no-op/unknown payloads. Confirm by reading state back and watching it
change (battery, `pauseSwitch`, `status`). Capturing what the app *sends* and
proving *you* can send it are two different things; do both.

## Quick reference (q287s6, as a worked example)

| apn | kind | body.data | meaning |
| --- | --- | --- | --- |
| 10001 | read | `{"fields":[...]}` | battery, state, fan, water, error, consumables |
| 40008 | write | `{"cleanSwitch":true,"cleanMode":"cleanBuilding"}` | start |
| 40009 | write | `{"pauseSwitch":true}` | pause |
| 40011 | write | `{"pauseSwitch":false}` | resume (separate apn from pause!) |
| 40013 | write | `{"chargeSwitch":true}` | return to dock |
| 50011 | write | `{"fanMode":"quiet\|strong\|max\|auto"}` | set suction |
| 50013 | write | `{"waterMode":"low\|mid\|high"}` | set water |

Note `mid` (not "medium"), and pause/resume being *different* apns — both were
inferred wrong first and only fixed by capturing the app. Trust the capture,
not the guess.

## Common mistakes

| Mistake | Reality |
| --- | --- |
| "Device returns null, so it's offline/broken" | Wrong transport. It's ngiot, not the legacy portal. |
| "Subscribe to MQTT `#` and watch" | ngiot broker is ACL-scoped — returns nothing. |
| "apn is the command name" | apn is numeric; names just echo the payload. |
| "Control goes to api-base" | api-base 404s for control; use the `mqs` host. |
| "code:0 means it worked" | Read state back; the device acks no-ops too. |
| "I'll infer the resume/dock payload" | They were both wrong when inferred. Capture them. |

## Next step

Once captured + verified, turn each surface into a real library command — see
**implementing-ngiot-deebot-commands**. Refs: DeebotUniverse/client.py#1569
(ngiot transport groundwork), #1642 (q287s6 request).
