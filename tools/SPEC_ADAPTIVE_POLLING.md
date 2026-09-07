# Spec: adaptive state polling

**Owner:** one agent; a real q287s6 is useful for verification but the change is
device-agnostic and unit-testable without one.
**Goal:** make state feel responsive without real-time push, by polling the
state-refresh command more often while the bot is active and backing off when
it's idle/docked. A single `GetState` read (apn 10001) returns all telemetry, so
one poll refreshes every entity cheaply.

## Why

Today `Device._available_task_worker` runs a fixed ~60s availability check.
Device-initiated changes (clean finished, error, battery) only surface on that
slow tick. Until ngiot push lands (separate spec), adaptive polling is the
pragmatic way to keep Home Assistant current. Optimistic updates already cover
*user-initiated* changes; this covers *device-initiated* ones.

## Design

All in `deebot_client/device.py`. Do not touch the command classes, the hardware
profiles, or `mqtt_client.py`.

- Add a state-refresh loop (e.g. `_state_refresh_worker`) started from
  `Device.initialize` (append a task; don't rewrite `initialize`).
- Pick the refresh command **generically** via
  `self.capabilities.get_refresh_commands(StateEvent)` — do not hardcode
  `GetState`, so this stays device-agnostic.
- Choose the interval from the last known state via
  `self.events.get_last_event(StateEvent)`:
  - active (`CLEANING` / `RETURNING` / `PAUSED`) → short interval (propose 10-15s)
  - idle / docked / unknown → slow interval (propose 60s)
  - back off on consecutive failures or `AvailabilityEvent(available=False)`.
- Expose the intervals as tunable constants and/or a `Device` constructor arg so
  HA and the maintainer can tune them.

### Don't regress legacy devices

A faster default poll across every existing device would surprise the
maintainer and the API. Default the active/idle intervals so existing behaviour
is unchanged unless explicitly opted in — e.g. gate the fast path behind a
constructor flag (default off) or a capability marker, and document the choice.
Confirm with the maintainer which they prefer.

## Interface / contract (keeps this independent of the push spec)

- Read state only via `self.events.get_last_event(StateEvent)`; emit nothing
  yourself — the refresh command produces the events.
- Touch only the refresh-cadence logic in `device.py`. The push agent also edits
  `device.py::initialize`; both only **append** there.
- No changes to `commands/`, `mqtt_client.py`, or the hardware profile.

## Tests

- With an injected/fake clock and a controllable interval, assert the loop polls
  at the active interval while state is `CLEANING`/`RETURNING`/`PAUSED` and at
  the slow interval when `DOCKED`/`IDLE`.
- Assert it executes the command returned by `get_refresh_commands(StateEvent)`
  (generic), not a hardcoded class.
- Assert a device without the opt-in keeps today's behaviour (no regression).
- Assert back-off when the device is unavailable.

Use the existing `tests/test_device.py` patterns; avoid real sleeps (inject the
interval / use the event loop's clock).

## Security

None new.

## Done when

- While the bot is cleaning, entities refresh within the active interval; once
  docked it reverts to the slow interval — shown live or via a deterministic
  unit test.
- Legacy devices are unchanged unless opted in.
- `uv run --frozen pytest`, `mypy deebot_client`, `ruff@0.15.15 check`+`format`,
  `codespell` all clean.

## Out of scope

ngiot MQTT push (separate spec), new transports, map/station telemetry.
