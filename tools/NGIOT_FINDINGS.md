# ngiot (q287s6 / DEEBOT NEO 2.0 PLUS) protocol findings

Live-verified 2026-06-28 against a real DEEBOT NEO 2.0 PLUS. Companion to
upstream issue DeebotUniverse/client.py#1642 and transport PR #1569.

Device: `class=q287s6`, `smartType=MQ_AP`, `UILogicId=y30plus_ww_h_y30h5`,
`company=eco-ng`, `fwVer=10.0.6`. Service block:
`jmq=jmq-ngiot-<region>.dc.ww.ecouser.net`, `mqs=api-ngiot.dc-<region>.ww.ecouser.net`.

## SOLVED — ngiot transport + SST auth work

Use `tools/ngiot_endpoint_probe.py`. Two steps:

**1. Mint an SST token** (HTTP 200):
```
POST https://api-base.dc-<region>.ww.ecouser.net/api/new-perm/token/sst/issue
Authorization: Bearer <account token>
Content-Type: application/json; charset=utf-8

{"acl":[{"policy":[{"obj":["Endpoint:q287s6:<did>"],"perms":["Control"]}],
  "svc":"dim"}],"exp":600,"sub":<user_id>}
-> {"code":0,"data":{"data":{"token":"SST.<jwt>..."}}}
```

**2. Call endpoint/control** (HTTP 200, `code:0`, `msg:"ok"`):
```
POST https://api-ngiot.dc-<region>.ww.ecouser.net/api/iot/endpoint/control
  query: si=<hex16> ct=q eid=<did> et=q287s6 er=<resource> apn=<cmd> fmt=j
  headers: Authorization: Bearer <SST>; x-eco-request-id=<si>;
           Content-Type: application/octet-stream; User-Agent: okhttp/4.9.1
  body (octet-stream JSON):
  {"body":{"data":{...}},
   "header":{"channel":"Android","m":"request","pri":2,"reqid":<6hex>,
             "ts":"<ms>","tzc":"UTC","tzm":0,"ver":"0.0.22"}}
```

> **Host note for PR #1569:** PR #1569 sends control to `service.mqs` and mints
> the SST on `api-base`, the same split as this branch. The
> `api-base.dc-<region>.ww.ecouser.net` host returns **HTTP 404
> "404 page not found"** for `endpoint/control` in the NA region. The
> `service.mqs` host (`api-ngiot.dc-<region>.ww.ecouser.net`) works. SST issue,
> however, IS served by the `api-base` host. So: SST from `api-base`, control
> from `mqs`.

## OPEN — the per-command `apn` catalog

Sending the device's own command names (`getBattery`, `getCleanInfo_V2`,
`getChargeState`, `getStationState`, `getAutoEmpty`, from a `getInfo` reply the
device sent to the Ecovacs STS helper) as `apn` just **echoes** the request body:
```
apn=getBattery body.data={}              -> data:{"data":{}}
apn=getBattery body.data={"type":["all"]}-> data:{"data":{"type":["all"]}}
```
Tried `ver` 0.0.9/0.0.1/0.0.22, `ct` q/r/c, numeric `apn`. All echo or empty.
The real `apn`/`ct`/`body.data` surface identifiers are the firmware's private
vocabulary and must be captured from the official app's traffic.

Dead ends confirmed: legacy `iot/devmanager.do` returns `code:0/data:null` for
everything (wrong transport — this is what crashed `message.py`, fixed separately);
`pim/product/getProductIotMap` lists the device but carries no command catalog.

## Capturing the app's apn values (next step)

`tools/mitm_ngiot.py` is a mitmproxy addon that logs `endpoint/control` calls.
mitmproxy alone is NOT enough: on Android 7+ the Ecovacs app rejects
user-installed CAs (TLS handshake fails for every `*.ecouser.net` / `*.ecovacs.com`
host). Needs one of:
- an Android emulator with the mitmproxy CA installed as a **system** cert, or
- **Frida SSL-unpinning** on a rooted device.

Once the app's real `apn` + `body.data` are captured, ngiot get-commands for
q287s6 can be implemented on top of PR #1569's transport and a hardware profile
added.

## Tools in this dir
- `ngiot_endpoint_probe.py` — mint SST + call endpoint/control (VERIFIED working).
- `ngiot_capture_live.py` — passive MQTT capture (returns nothing; broker is
  ACL-scoped — kept for reference).
- `ngiot_capture_wild.py` / `ngiot_probe.py` — earlier diagnostic helpers.
- `mitm_ngiot.py` — mitmproxy addon to capture app `endpoint/control` traffic.

---

## Headless capability feedback loop (tools/ngiot_capability_loop.py)

The app-capture path is flaky (the app goes offline under MITM; map/control screens are
WebViews). But we don't need the app to map most surfaces: `apn=10001` is a unified
field-query oracle, and the device answers it headlessly via plain SST + endpoint/control.

The loop (no app, no MITM, no emulator):
- READ discovery: ask 10001 for a union of candidate field names. A **non-null value** is a
  confirmed read surface. (A `null` value means the device knows the key but isn't reporting
  it in the current state -- many are state-dependent, e.g. `waterMode` only populates while
  cleaning, station fields only when docked to an auto-empty station.)
- WRITE discovery: `set -> read-back -> diff`. Send a candidate `(apn, payload)`, then read the
  affected field via 10001 and compare. CRITICAL: the device returns `code:0` for accepted-
  but-ignored writes (wrong key / non-surface apn), so `code:0` proves nothing -- only an
  observable field change confirms a real control surface.

Usage:
    source ~/.ecovacs.env
    uv run --frozen python tools/ngiot_capability_loop.py fields          # read vocabulary
    uv run --frozen python tools/ngiot_capability_loop.py read a,b,c       # specific fields
    uv run --frozen python tools/ngiot_capability_loop.py setcheck <apn> '<json>' <field>
    uv run --frozen python tools/ngiot_capability_loop.py sweep <field> <val> <apn0> <apn1> [step]

### Mapped so far (2026-06-28, device docked/idle)

Confirmed NON-NULL read surfaces via 10001:
  battery, chargeStatus, childLock, cleanArea, cleanCount, cleanTime, consumables (4
  life-spans), error, fanMode, mopState, pauseSwitch, status, volume(=8), waterMode, workMode.
New vs. what the profile wires today: **volume** and **childLock** are confirmed-real and
not yet wired.

Known-but-null right now (state-dependent; need the right device state to populate):
  advancedMode, aiavoid, autoEmpty, borderSpin, carpetPressure, continuousClean,
  dryingDuration, mopAutoWash, sound, speaker, stationInfo, stationStatus, stationType,
  sweepMode, trueDetect, trueDetectAvoid, voiceReport.

### Write-surface discovery status
`set->read-back->diff` works and correctly rejects code:0 echoes. But the write-apn search
space is large (apn x payload-key x value-shape). A `{volume:N}` sweep of 50000-50040
found many code:0 (accept-and-ignore) and NO real change, so the volume *set* apn is not in
that range / uses a different shape. There is no self-describing manifest field (apnList,
supportApn, etc. all return null). So write mapping is feasible but slow by fuzzing;
the app capture would still be the fast oracle for set-apns if the offline issue is solved.
