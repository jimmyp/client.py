# q287s6 manual confirmation checklist

For the walkthrough session. Goal: confirm what's already verified, then capture the
**set-apns** we still don't have so we can wire the remaining capabilities (volume,
child-lock, play-sound, life-span reset) for real.

Safety: the agent must **not** drive the vacuum unprompted. The capability-loop tool
(`tools/ngiot_capability_loop.py`) has a hard guard that refuses motion/clean/dock keys.

---

## 1. Confirm what's already done (no device motion)

```bash
source ~/.ecovacs.env
cd <worktree or repo>

# (a) full automated suite + gates
uv run --frozen pytest -q                 # expect 755 passed
uv run --frozen mypy deebot_client        # expect clean
uvx ruff@0.15.15 check deebot_client tests # expect clean

# (b) headless read map of the live device (no writes)
uv run --frozen python tools/ngiot_capability_loop.py fields
#   expect NON-NULL: battery, fanMode, waterMode, status, volume, childLock,
#   consumables, error, etc. NULLs are state-dependent (see findings).
```

Already verified earlier (in tools/Q287S6_TEST_REPORT.md): state read, start/stop/
pause/resume/dock, set-fan, set-water -- all live-confirmed end-to-end.

## 2. Capture the missing SET surfaces (the actual goal)

The read side is fully mappable headlessly; the **set apns are not** (not in 50000-50099,
no manifest). Two ways to get them:

### Option A -- app capture (preferred if the app stays online)
Bring up the rig (see tools/NGIOT_FINDINGS.md "Bring the capture/test rig back up"),
get the app ONLINE (the recurring blocker), then in the app tap:
- **Volume** slider -> capture apn + payload (expect `{volume:N}` on some apn)
- **Child lock** toggle -> apn + `{...}`
- **Find robot / play sound** -> apn + payload
- **Reset** a consumable counter (Maintenance) -> apn + payload
Each tap lands in `ngiot_app_capture.jsonl`; read the apn + body.data.

### Option B -- guided write-probe (device present, you watching)
With the user watching the physical bot, use the loop's setcheck/sweep to find a
set-apn by read-back diff. Example (volume is audible-only, safe):
```bash
uv run --frozen python tools/ngiot_capability_loop.py setcheck <apn> '{"volume":3}' volume
#   REAL = volume actually changed (not just code:0)
```
The guard blocks motion keys, so only settings-style writes go through.

## 3. Wire each captured surface (per the implementing-ngiot-deebot-commands skill)

For each confirmed set-apn:
1. Add a real `NgiotSetCommand` (model on `commands/ngiot/settings.py` SetFanSpeed).
2. Add a wire-contract test pinning the exact apn + body.data
   (`tests/commands/ngiot/test_wire_contract.py`).
3. Mutation-check the test (revert apn -> test must fail).
4. Wire it into `hardware/q287s6.py` (volume -> CapabilitySettings.volume, etc.),
   replacing the not-supported stub.
5. Live-verify (read the value back changed).
6. Run full suite + mypy + ruff + codespell. Commit.

## Current state (start of session)
- Profile wires: battery, charge, clean(start/stop/pause/resume), error, fan_speed,
  life_span(read; reset=stub), play_sound(stub), state, water(amount+mop), stats(empty),
  network(empty), custom(stub). map/station: not implemented (capture blocked).
- volume/childLock: confirmed REAL reads, NOT yet wired (need set-apn; see memory).
- Tools: ngiot_capability_loop.py (headless discovery, motion-guarded),
  ngiot_q287s6_live.py (e2e), mitm_ngiot.py (app capture addon).
