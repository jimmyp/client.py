---
name: implementing-ngiot-deebot-commands
description: Use when turning a captured Ecovacs ngiot protocol (numeric apn surfaces + endpoint/control) into deebot-client command classes, wiring them into a hardware profile, and writing tests that prove the exact wire payload.
---

# Implementing ngiot deebot-client commands

## Overview

You have a captured ngiot surface (e.g. `apn=50011`, write `{"fanMode":"quiet"}`).
Turn it into a real `deebot_client` command on the ngiot base classes, wire it
into the device's hardware profile, and pin the **exact bytes on the wire** with
a test. Reads use `body.data = {"fields":[...]}`; writes use `{key: value}`.

## The real seam (don't invent an API)

ngiot commands go through `NgiotClient.control(device_info=, apn=, data=)` —
that is the one boundary, and the one to assert against. The base classes in
`deebot_client/commands/ngiot/common.py`:

- `NgiotGetCommand(fields=[...])` — read; parses `body.data` into events.
- `NgiotExecuteCommand(data)` — action; success = envelope `code`.
- `NgiotSetCommand` — write linked to a get command for optimistic updates.

A write command is just an `apn` + a `body.data` dict:
```python
class SetFanSpeed(NgiotSetCommand):
    NAME = "setFanSpeed"
    APN = 50011
    def __init__(self, speed: FanSpeedLevel) -> None:
        super().__init__({"fanMode": NGIOT_LEVEL_TO_FAN_MODE[speed]})
```
Model new commands on the existing `clean.py` / `settings.py` / `state.py`.

## Map enums from the WIRE values, not assumptions

The device's enum strings are exactly what you captured — and they surprise you:
`waterMode` is `"mid"` (not `"medium"`), fan has `"auto"` as its default, and
pause/resume are *different* apns. If a captured wire value has no mapping, the
event is silently dropped — so map every value you saw, and **log a WARNING on
an unmapped value** rather than dropping it.

## Wire into the hardware profile

The device won't expose an action until it's in `deebot_client/hardware/<class>.py`
`Capabilities`. Point each capability at the ngiot command (e.g.
`fan_speed=CapabilitySetTypes(set=SetFanSpeed, get=[GetState()], ...)`). For
slots required by the schema but with no captured surface, use explicit
not-supported stubs (no network, `device_reached=False`, log a warning) — never
the legacy JSON commands, which silently fail on this transport.

## Test the bytes on the wire (the non-negotiable test)

Object-construction tests pass even when serialization is wrong. There are three
layers; the third is the one people skip:

1. **Command -> transport** (mock `ngiot.control`, assert `apn`/`data`).
2. **Transport -> wire** (real `NgiotClient` over a fake session, assert the
   serialized request: host, query params, octet-stream envelope, header `ver`).
3. **Command -> wire contract** (the gap): drive the **real command class**
   through the **real `NgiotClient`** over a fake session, and assert the
   captured POST matches the **exact captured payload** — host, numeric `apn`,
   `body.data`. This is what catches a wrong apn or a wrong enum string.

```python
class _FakeSession:
    def __init__(self, responses): self._r = list(responses); self.calls = []
    def post(self, url, **kw): self.calls.append((url, kw)); return self._r.pop(0)
# run command._execute(auth_with_real_NgiotClient, device_info, event_bus)
# then: url, kw = session.calls[0]; body = orjson.loads(kw["data"])
# assert kw["params"]["apn"] == "50011"
# assert body["body"]["data"] == {"fanMode": "quiet"}
```

See `tests/commands/ngiot/test_wire_contract.py` for the full parametrized form.

## Prove the test actually catches the bug (mutation check)

After it's green, **temporarily** revert the command to a wrong value (e.g. the
old apn) and confirm the wire test fails. A wire test that can't fail on a wrong
apn isn't testing the wire. Restore immediately.

## Verify live, never claim without evidence

Run the command class against the real device
(`tools/ngiot-reverse-engineering/verify/q287s6_live_e2e.py`) and watch state
change. `code:0` alone is not proof — the device acks no-ops. Don't mark a
surface "working" without a live read-back.

## Common mistakes

| Mistake | Reality |
| --- | --- |
| Invent `cmd.apn`/`payload["data"]` API | The seam is `NgiotClient.control(apn=, data=)`. |
| Assert on the Python object | Serialization can still be wrong. Assert the POST. |
| Skip the command->wire test | Layers 1&2 miss a wrong apn/enum on a real command. |
| Guess enum strings | Use captured wire values (`mid` not `medium`, etc.). |
| Drop unmapped enum silently | Log a WARNING; otherwise the event vanishes. |
| Legacy JSON for unsupported slots | Silently fails on ngiot. Use explicit no-op stubs. |
| "code:0, ship it" | Read state back live before claiming it works. |

REQUIRED BACKGROUND: **capturing-ecovacs-ngiot-protocol** (where the apn catalog
comes from). Refs: DeebotUniverse/client.py#1569, #1642.
