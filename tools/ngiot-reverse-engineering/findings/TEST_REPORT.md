# q287s6 ngiot integration — manual test report & automated coverage

**Date:** 2026-06-28
**Branch:** `claude/ngiot-q287s6-e2e-c37o72` (PR #3)
**Device under test:** real DEEBOT NEO 2.0 PLUS (`q287s6`), fw 10.0.6, AU account
**Method:** the new command classes driven against the live device (read-only +
a full control cycle), plus targeted raw `endpoint/control` probes and a second
official-app capture (Frida-unpinned app on an Android emulator, via mitmproxy).

## Summary

The integration is **working end-to-end and live-verified**. Manual testing
found three real defects — all in inferred values the unit tests had baked in as
assumptions — which are now fixed, live-confirmed, and guarded by new automated
tests.

| Area | Result |
| --- | --- |
| Device recognition (appears in `devices.mqtt`) | ✅ |
| SST mint + `endpoint/control` on the **mqs** host | ✅ |
| `GetState` (apn 10001) parsing → events | ✅ |
| Clean start / stop / pause / **resume** / **dock** | ✅ (after fixes) |
| Fan / water reporting | ✅ (after fixes) |

## What was verified live

`tools/ngiot-reverse-engineering/verify/q287s6_live_e2e.py` and ad-hoc probes, run with real credentials:

- **Read (idle/docked):** `BatteryEvent(100)`, `StateEvent(DOCKED)`,
  `MopAttachedEvent(True)`, `ErrorEvent(0, NoError)`, four `LifeSpanEvent`s
  (sideBrush 26%, brush 50.67%, filter 84.67%, unitCare 20%).
- **Control cycle:** START → device `smartClean`; PAUSE → `pauseSwitch:true`;
  RESUME → back to cleaning; DOCK → `status:"goCharge"`. Each confirmed by a
  read-back of real device state, not just the optimistic event.
- **While cleaning:** `FanSpeedEvent` and `WaterAmountEvent` now emit (battery
  even ticked 100→99 as it genuinely cleaned).

## Defects found and fixed

1. **Fan speed never surfaced.** The device's default `fanMode:"auto"` was not
   in the enum map, so `GetState` silently emitted no `FanSpeedEvent`. Fixed:
   map `"auto"` → `FanSpeedLevel.NORMAL` (no dedicated AUTO level exists), and
   log unmapped values instead of dropping them. *(commit 25780b0)*
2. **Water amount never surfaced.** Real wire value is `waterMode:"mid"`; the
   code had the inferred `"medium"`, so the lookup missed and no
   `WaterAmountEvent` was emitted. Fixed to `"mid"`. *(commit 25780b0)*
3. **Resume and dock used the wrong surfaces.** Resume was inferred as
   `40009 {pauseSwitch:false}` — the device returns `code:1` and does not
   reliably resume. The app actually uses a **separate apn, `40011`**. Dock was
   inferred as `40015 {chargeSwitch:false}`; the app uses `40013
   {chargeSwitch:true}`. Both corrected and confirmed live. *(commit 6b264bc)*

Root pattern: the original implementation correctly captured the *reads* and the
start/stop/pause/fan/water *writes*, but the values it could not observe in the
first capture (resume, dock, and default enum strings) were inferred — and the
inferences were wrong. Live exercise + a second targeted capture resolved them.

## Wire-verified enum values

- `fanMode`: `auto` (default), `quiet`, `strong`, `max`
- `waterMode`: `low`, `mid` (**not** "medium"), `high`
- `waterMode` is **omitted by the device while docked**; it is only reported
  while cleaning. (So a docked read legitimately has no `WaterAmountEvent`.)

## Automated testing — "correct payloads on the wire"

This was the explicit goal. Coverage now exists at three layers:

1. **Command → transport (pre-existing):** `assert_ngiot_command` mocks
   `Authenticator.ngiot.control` and asserts each command passes the right
   `apn` + `body.data`. Catches command-logic regressions.
2. **Transport → wire (pre-existing):** `tests/test_ngiot_client.py` drives the
   real `NgiotClient` over a fake aiohttp session and asserts the *serialised*
   request — mqs host (not api-base), query params (`apn/eid/et/er/fmt`),
   octet-stream JSON envelope, `header.ver`, `x-eco-request-id` correlation, and
   that the SST token is never logged. Catches transport-serialisation
   regressions, but with *generic* apn/data.
3. **Command → wire contract (NEW — `tests/commands/ngiot/test_wire_contract.py`):**
   the gap between (1) and (2). Each real command class (`Clean(START/STOP/PAUSE/
   RESUME)`, `Charge`, `SetFanSpeed`, `SetWaterAmount`, `GetState`) is run
   end-to-end through the real `NgiotClient`, and the captured POST is asserted
   against the **exact live-captured wire payload** — host, numeric `apn`,
   `body.data`, octet-stream envelope, SST bearer. This is the test that pins
   "the right bytes go on the wire for each command."

**Does it actually catch the bugs?** Verified by mutation: reverting resume to
the buggy `40009` makes `test_wire_contract.py::...[resume]` fail with
`- 40011 / + 40009`. So this layer would have caught all three defects above
before they shipped.

### What automated tests can and cannot cover

- **Can (and now do):** exact wire payload per command; transport host/envelope;
  response parsing → events using the real captured `body.data`; SST hygiene.
- **Cannot (needs the live device or an app capture):** that a given `apn`/payload
  *actually* makes the physical device do the thing (the device returns `code:0`
  for some no-op/unknown payloads, so "accepted" ≠ "correct"); the full set of
  valid enum values; new/unknown surfaces. These remain manual / capture-driven.
  `tools/ngiot-reverse-engineering/verify/q287s6_live_e2e.py` is the repeatable live check for when a device +
  credentials are available.

## Test run

- `uv run --frozen pytest` → **737 passed** (full suite).
- `tests/commands/ngiot/` → 31 passed (incl. 10 new wire-contract cases).
- `ruff@0.15.15 check` + `format --check` clean; `mypy` clean on changed files.
- Live: full start→pause→resume→dock cycle succeeded; bot returned to dock.
