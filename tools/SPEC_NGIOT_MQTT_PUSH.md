# Spec: ngiot real-time MQTT push for q287s6

> **SUPERSEDED (2026-06-30).** An instrumented trace of the official app (PR #5)
> found the q287s6 has **no native push channel**: its only MQTT connection is
> Aliyun account-binding, and the app's control UI reads live state through the
> same REST `GetState` (apn 10001) this library already calls. There is no `jmq`
> push to capture. Real-time state for this device is polling — see
> `SPEC_ADAPTIVE_POLLING.md` (PR #4). This spec is kept only for history and in
> case a *different* ngiot device turns out to expose push.

**Owner:** one agent, needs a real q287s6 + the app/MITM capture rig.
**Goal:** device-initiated state changes (clean finished, error raised, battery
drained, docked) reach Home Assistant in real time, instead of only on the next
poll. Today q287s6 control is REST (`endpoint/control`) and state comes from
polling `GetState` (apn 10001); there is no push.

## Why it isn't wired yet

`deebot_client/mqtt_client.py` is built for the legacy broker only:

- It connects to one account-wide host, `mq{continent}.ecouser.net`
  (`create_mqtt_config`). ngiot devices push on a **per-device** host from the
  API device record: `device.api["service"]["jmq"]`
  (e.g. `jmq-ngiot-<region>.dc.ww.ecouser.net`).
- It subscribes to legacy topics (`iot/atr/...`, `iot/p2p/...`). ngiot's topic
  namespace on the jmq broker is different and uncaptured.
- A prior passive capture got nothing: the jmq broker is ACL-scoped, so the
  subscription needs the right credentials + topic filters.

The bundled CA already covers the `*.dc.ww.ecouser.net` ngiot hosts (see the
SSL-context comment in `mqtt_client.py`), so TLS is ready; nothing connects to
the jmq broker.

## Phase 1 — capture (device + rig required)

Extend the existing rig (`tools/mitm_ngiot.py`, `tools/CAPTURE_RIG_RECIPE.md`)
to the MQTT/WebSocket session, driving the official app while the bot changes
state. Capture and record in a new "MQTT push" section of
`tools/NGIOT_Q287S6_PROTOCOL.md` (redact tokens/ids/mac/sn):

1. **Broker**: exact host (confirm it's `service.jmq`), port, and transport
   (MQTT-over-TLS vs MQTT-over-WebSocket).
2. **CONNECT**: client-id format, username, password (account token? a minted
   SST? a derived credential?), keepalive, clean-session.
3. **SUBSCRIBE**: the exact topic filter(s) the app subscribes to for this
   device (the ngiot equivalent of `iot/atr`/`iot/p2p`).
4. **PUBLISH (push)**: 3-4 messages the broker sends when state changes — record
   topic + payload. Critically: **is the payload the same `body.data` shape that
   `endpoint/control` returns** (flat field dict), or a different envelope? This
   decides whether the existing state parser can be reused.

## Phase 2 — implement

Reuse the event pipeline; do **not** touch the command layer or `GetState`'s
public behaviour.

- Add per-device ngiot broker support. The current `MqttClient` is one
  connection for the whole account; ngiot needs a connection keyed off
  `service.jmq`. Prefer a parallel `NgiotMqttClient` (own connection, reusing
  `_ecovacs_ssl_context()` and the credential the capture revealed) over
  overloading the legacy client, unless the capture shows the legacy broker also
  carries ngiot topics.
- Translate a pushed payload into events. If Phase 1 shows the push payload is a
  `body.data` field dict, factor the field-fan-out out of
  `GetState._handle_body_data_dict` into a module-level
  `handle_state_fields(event_bus, data)` in `commands/ngiot/state.py` and call it
  from both `GetState` and the push handler. (This is the one shared edit with
  the polling spec — coordinate: whoever lands first adds the helper.)
- Subscribe on `Device.initialize` for ngiot devices (in addition to the
  availability check). Append a subscription step; don't rewrite `initialize`.

## Interface / contract (keeps this independent of the polling spec)

- Output is **only** `event_bus.notify(...)` of the existing events, exactly as
  `GetState` does. No new event types.
- Do not change command classes, the hardware profile, or polling cadence.
- The only file the polling agent also edits is `device.py` (`initialize`);
  both only **append** a task/subscription there.

## Tests (no live secrets in fixtures)

- Broker host derived from `service.jmq` (not the legacy `mq{continent}` host).
- Subscription topic(s) built correctly from a device record.
- A captured push sample → the correct events (reuse the `body.data` fixture
  style in `tests/commands/ngiot/test_state.py`).
- Credential/token never logged (mirror `test_token_is_never_logged`).

## Security

- Use the verifying SSL context (`CERT_REQUIRED` against the bundled CA). Never
  `CERT_NONE`.
- Whatever credential the broker needs (token/SST), treat with SST-grade
  hygiene: never logged, short-lived where possible, minimal scope.

## Done when

- Driving the bot from the app (or letting it finish a clean) produces the
  matching events within seconds, with no poll — shown live.
- `uv run --frozen pytest`, `mypy deebot_client`, `ruff@0.15.15 check`+`format`,
  `codespell` all clean.
- The MQTT push protocol is documented in `tools/NGIOT_Q287S6_PROTOCOL.md`.

## Out of scope

Polling cadence (separate spec), map/station telemetry, legacy-device push.
