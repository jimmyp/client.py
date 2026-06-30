# q287s6 (DEEBOT NEO 2.0 PLUS) ngiot protocol — CAPTURED FROM OFFICIAL APP v3.13.0

Captured 2026-06-28 via Frida-unpinned Ecovacs app on an Android emulator,
MITM through mitmproxy. Device class q287s6, fwVer 10.0.6.

Transport (verified): mint SST at api-base.dc-na.ww.ecouser.net, then
POST https://api-ngiot.dc-na.ww.ecouser.net/api/iot/endpoint/control
query: si,ct=q,eid=<did>,et=q287s6,er=<res>,apn=<NUMERIC>,fmt=j ; header ver=0.0.22.
KEY INSIGHT: apn is a NUMERIC surface id, not a command name. Reads use
body.data={"fields":[...]}; writes use body.data={key:value}.

## Surfaces ( 16 distinct)

### apn=10001  [GET]
```
REQ body.data: {"fields": ["otaData"]}
RESP body.data: {"otaData": {"failedCode": 0, "otaInfo": {"progress": 100, "ver": ""}, "otaRst": 0, "otaStatus": "done"}}
```

### apn=10001  [GET]
```
REQ body.data: {"fields": ["status"]}
RESP body.data: {"status": "smartClean"}
```

### apn=10001  [GET]
```
REQ body.data: {"fields": ["stationType", "stationStatus", "cleanValues", "chargeStatus", "pauseSwitch", "battery", "disturbSwitch", "disturbTimeSet", "mopState", "workMode", "breakCleanStatus", "fanMode", "waterMode", "cleanCount", "error", "consumables", "newMapReport", "expandedMapReport", "cleanLogReport", "deviceInfo", "childLock", "isEurope", "cleanTime", "cleanArea", "silentOtaSwitch", "nextSchedule", "dormant", "relocateSwitch", "unitSet", "otaData", "voiceData", "timeZone"]}
RESP body.data: {"battery": 100, "breakCleanStatus": false, "chargeStatus": false, "childLock": false, "cleanArea": 0, "cleanCount": 1, "cleanLogReport": {"cid": "<redacted>", "resource": "<resource>"}, "cleanTime": 0, "cleanValues": null, "consumables": [{"left": 3120, "total": 12000, "type": "sideBrush"}, {"left": 9120, "total": 18000, "type": "rollBrush"}, {"left": 7620, "total": 9000, "type": "filter"}, {"left": 360, "total": 1800, "type": "unitCare"}], "deviceInfo": {"fwVersion": "10.0.6", "ip": "<redacted-ip>", "mac": "<redacted-mac>", "mcuVersion": "A09274.083.517", "rssi": "xxx", "sn": "xxxxxx", "ssid": "xxx", "wkVersion": "0.0.9"}, "disturbSwitch": false, "disturbTimeSet": {"endHour": 8, "endMin": 0, "startHour": 22, "startMin": 0}, "dormant": false, "error": [0], "fanMode": "strong", "isEurope": null, "mopState": "installed", "nextSchedule": null, "otaData": {"failedCode": 0, "otaInfo": {"progress": 100, "ver": ""}, "otaRst": 0, "otaStatus": "done"}, "pauseSwitch": false, "relocateSwitch": true, "silentOtaSwitch": true, "stationStatus": null, "stationType": null, "timeZone": 600, "unitSet": "squareMeter", "voiceData": {"downloads": [{"id": "", "md5": "", "name": "", "progress": 100, "size": 0, "status": "down"}], "id": "EN", "md5": "", "name": "English", "size": 100, "url": ""}, "waterMode": "low", "workMode": "auto"}
```

### apn=10001  [GET]
```
REQ body.data: {"fields": ["timeZone", "deviceTimer"]}
RESP body.data: {"deviceTimer": [{"cleanValues": [2, 1], "hour": 2, "id": "88120", "mapId": "2", "min": 0, "on": 0, "repeat": "0000000", "state": 3, "type": "area"}, {"cleanValues": null, "hour": 10, "id": "576842", "mapId": null, "min": 42, "on": 0, "repeat": "0111110", "state": 0, "type": "auto"}, {"cleanValues": null, "hour": 15, "id": "88072", "mapId": null, "min": 0, "on": 0, "repeat": "1111111", "state": 0, "type": "auto"}], "timeZone": 600}
```

### apn=30001  [GET]
```
REQ body.data: {"fields": ["mapStatus"]}
RESP body.data: {"mapStatus": "mappingDone"}
```

### apn=30001  [GET]
```
REQ body.data: {"fields": ["mapInfos"]}
RESP body.data: {"mapInfos": [{"angle": 0, "chargePos": {"a": 4, "x": -50, "y": 195}, "index": 1, "mapId": "2", "name": "", "saved": 1, "status": 0}, {"angle": 0, "chargePos": {"a": 1, "x": -100, "y": -215}, "index": 2, "mapId": "3", "name": "", "saved": 1, "status": 0}, {"angle": 0, "chargePos": {"a": 2, "x": -105, "y": -120}, "index": 3, "mapId": "4", "name": "", "saved": 1, "status": 0}, {"angle": 0, "chargePos": {"a": 357, "x": -135, "y": 110}, "index": 4, "mapId": "5", "name": "", "saved": 1, "status": 1}]}
```

### apn=30001  [GET]
```
REQ body.data: {"mapId": "5", "fields": ["mapTraceData"]}
RESP body.data: {"mapId": "5", "mapTraceData": {"lz4Len": 0, "mapId": "5", "start": 0, "totalCount": 0, "trace": "", "traceId": "<redacted>"}}
```

### apn=30001  [GET]
```
REQ body.data: {"mapId": "5", "fields": ["virtualWalls", "mopWalls", "carpets"]}
RESP body.data: {"mapId": "5", "mopWalls": "", "virtualWalls": ""}
```

### apn=30001  [GET]
```
REQ body.data: {"mapId": "5", "fields": ["mapData", "areas", "pos"]}
RESP body.data: {"areas": [{"centerX": -210, "centerY": 365, "id": 1, "name": "", "type": ""}, {"centerX": 205, "centerY": 425, "id": 2, "name": "", "type": ""}, {"centerX": 95, "centerY": 115, "id": 3, "name": "", "type": ""}], "mapData": {"chargePos": {"a": 357, "x": -135, "y": 110}, "direction": -1, "height": 183, "lz4Len": 29829, "map": "H38BAP///8cfAAEAIQ8MBFsvAAEBAB8PowD//////////9cBhgkP6giLAoUJBAgADwIAVg8wChkPowCWEQDwAQ8CAFgPRgEeAEkMD6AAWA+jAB0A6gEUAPEBDwIAVg9GARkQAUIBD6MAjAMCAABNAQ8CAFgPRgEaAwIAD6MA/9sBOgMOAgAPowJBD4wCJQ84AAMPpgJCD2sAAw8CAAsBPQEPIwACD6MAUgH5BAQCAA/AAB4PowBTCJgACbAADwIAEQ+jAPYPZgIEDwIAEw9GAVIPAgArD6MA//+TEgAyBw8fByMHBgUPAgAwDy8DBQCQBiACAgYADwIACw/EAAIPowBUHwIBABIP4gADD6MA/////7UBmgUOgQUfABcFEg8YBVIBAgAPaQAAD6MAeQBLDA+jAIsvAAB/FAMPRgF4D0EBAAECAA+jAD4ArgEBVgIPAgAeD6MATwSaAA9jDSYPowBPDwIALg+jAP//uA/JAgYPIwMuCAIAD2YABg+kBxEPPQAGCGIABQIABH4EDwIAHQ9mAAYPowA3A5sAD7wFJg+jAC0PQAACA5UAAgIABLMFD6MAZA/sAQQJowAMAgAA/gkMFAAAAgAPGAAFHwEGAQIAxxsP6QESD6MAFgeWAABNGwCTAAwCAAAAEQwUAAECAA+jAAYAjRAPAgAND6MAIw/yAQQPowAeD+wIEiAAAikADgIADukBCEYBDh4AAAIAACwBDxoABw8CAAMPjwkQD0YBFw8CAA8PowDpD5oNAQ+xAQUPAgALD0YBRA8uAwQAbAMHfQIPAgAFACUABAIAD6MAXgACAA/7AgMHAgAAmAAEAgAAiQQA2wAEEAAJAgAAYAEPAgADDS8DBPIACQIADzwAAw9vAAYGAgAIogAAKQUAiQAP1wADABoADwIAAwyjAA+PAAgPAgAACYIADwIAAQiPAAAtAACJAAgUAAYCAAAaAA8CAAMNowAPJwADDwIABA9uAAMHAgAAIQAABAAEAgAAiQAIEAAGAgAAGgAPAgADD6MAJwEKAgZjAA8CAAMAfwIIkwAAiQAIEAAGAgAAGgAPAgADD6MAKAZfAA8CAAcaAKIADy8DMg/NAAcMAgAPDQEDCwIADKoHAF8ADzkAAwAaAA8CAAMPRgFMDAIAAIkAD6MAHhr/AQAARAAPAgAT
```

### apn=40002  [SET]
```
REQ body.data: {"cleanSwitch": false}
RESP body.data: null
```

### apn=40008  [SET]
```
REQ body.data: {"cleanSwitch": true, "cleanMode": "cleanBuilding"}
RESP body.data: null
```

### apn=40009  [SET]
```
REQ body.data: {"pauseSwitch": true}
RESP body.data: null
```

### apn=40015  [SET]
```
REQ body.data: {"chargeSwitch": false}
RESP body.data: null
```

### apn=50011  [SET]
```
REQ body.data: {"fanMode": "quiet"}
RESP body.data: null
```

### apn=50013  [SET]
```
REQ body.data: {"waterMode": "high"}
RESP body.data: null
```

### apn=getInfo  [?]
```
REQ body.data: ["getCleanInfo", "getCleanInfo_V2", "getBattery", "getStationState", "getChargeState", "getAutoEmpty"]
RESP body.data: {"data": ["getCleanInfo", "getCleanInfo_V2", "getBattery", "getStationState", "getChargeState", "getAutoEmpty"]}
```

---

## Update: control commands captured from the app + confirmed on device (2026-06-28)

A second app capture + live confirmation corrected three inferred commands:

- **PAUSE**: apn `40009` `{"pauseSwitch": true}`  (was correct)
- **RESUME**: apn **`40011`** `{"pauseSwitch": false}`  -- a SEPARATE apn from pause;
  the earlier inferred `40009 {pauseSwitch:false}` returned `code:1` and did not
  reliably resume. `40011` returns `code:0` and resumes (confirmed: pauseSwitch
  true->false while cleaning).
- **RETURN TO DOCK**: apn **`40013`** `{"chargeSwitch": true}`  -- not the earlier
  `40015 {chargeSwitch:false}`. `40013` returns `code:0` and the device reports
  `status:"goCharge"`.

Other write surfaces seen from the app (not yet wired): `30007 {expandedMapReport:""}`
(map report request).

Fan/water enum values actually emitted by the app (wire-verified):
- fanMode: `auto` (default), `quiet`, `strong`, `max`
- waterMode: `low`, `mid` (NOT "medium"), `high`

## Update: 4 setting set-apns captured from the app (2026-06-29)

Captured live via Frida-unpinned app + mitmproxy on the emulator (the rig finally worked
after fixing screen size + reinstalling app/frida-server; the earlier "no network" was a
broken in-guest curl test, not a real network failure). All returned code:0; values verified
against the read oracle.

| Command | apn | write payload | read-back field |
|---|---|---|---|
| Set volume | 50023 | `{"volume": <int 0..N>}` | `volume` |
| Play sound / locate robot | 40019 | `{"seek": true}` | (momentary) |
| Child lock | 50038 | `{"childLock": <bool>}` | `childLock` |
| Reset consumable | 50017 | `{"resetConsumable": "<type>"}` | `consumables[].left` |

`resetConsumable` types (from the consumables read surface): `sideBrush`, `rollBrush`,
`filter`, `unitCare`.

## MQTT push (jmq broker) — architecture understood, live wire NOT yet captured (2026-06-30)

Goal: device-initiated state changes pushed in real time (vs. polling apn 10001).
Spec: tools/SPEC_NGIOT_MQTT_PUSH.md.

### Established this session (verified)
- **Broker host**: `service.jmq` = `jmq-ngiot-na.dc.ww.ecouser.net`, which resolves to
  `slb-mq-iot-na.ww.ecouser.net` (43.110.16.x), port **443**. Reachable from the guest
  (TCP connect + ICMP OK after fixing emulator clock skew).
- **MQTT stack**: the app uses **stock Eclipse Paho Java** — unshaded
  `org.eclipse.paho.client.mqttv3.*` classes are loaded (ClientState, ClientComms,
  CommsReceiver, internal.wire.MqttConnect/MqttSubscribe/MqttPublish, MqttConnectOptions),
  wrapped by `com.aliyun.alink.linksdk.*` (Aliyun LinkKit). So the MQTT bytes ride a Java
  `SSLSocket`, NOT the system `libssl.so` used by OkHttp.
- **Why native SSL hooks fail**: hooking `libssl.so` `SSL_read`/`SSL_write` (BoringSSL)
  captures nothing — the Paho `SSLSocket` path doesn't go through those exports. Confirmed
  across 5 native attempts (hook installs, 0 MQTT bytes). The correct interception layer is
  **Java Paho**, above TLS (see tools/frida_paho_capture.js).
- **Correct hook points** (verified to install cleanly via attach-mode):
  `ClientState.send(MqttWireMessage, MqttToken)` for outbound (CONNECT/SUBSCRIBE/PUBLISH),
  `MqttConnect.<init>(...)` for CONNECT credentials (clientId/username/password — password
  is a char[] here, redact to length), and `ClientState.notifyReceivedMsg(MqttWireMessage)`
  for inbound pushes.

### The remaining blocker (rig, not understanding)
The app **does not hold the jmq MQTT connection alive under the instrumented emulator**.
With Paho hooks installed and live, 50s produced no PINGREQ heartbeat, and a real
device-side change (volume 8->5 via the SST transport) produced **no inbound push** to the
app. Inspecting `/proc/<pid>/net/tcp*` showed the app had **no TCP connection to the broker
(43.110.16.x)** at all — only DNS-over-TLS to 10.0.2.3:853. The "Online" status seen in the
UI came from a brief/earlier connection or REST, not a sustained MQTT link. This matches the
long-standing rig fragility (see memory q287s6-capture-lessons): the app's MQTT presence
connection is unreliable under frida/emulator.

### What's needed to finish Phase 1
A rig where the app **keeps** the jmq connection open: most likely a **physical rooted
device** (where the app + LinkKit MQTT run normally) with `tools/frida_paho_capture.js`
attached. On a working connection the Java hooks will yield CONNECT (client-id/username,
redacted password), the SUBSCRIBE topic filter(s), and the inbound PUBLISH topic+payload —
the last answers the key question: **is the push payload the same `body.data` field-dict
shape as endpoint/control** (if so, `handle_state_fields()` parses it directly).

### Capture tooling (committed)
- `tools/frida_paho_capture.js` — Java-layer Paho hook (the correct approach; installs cleanly).
- `tools/frida_mqtt_capture.js` + `tools/decode_mqtt_capture.py` — native SSL-bytes approach
  (kept for reference / other apps; does not capture this app's Paho-over-SSLSocket MQTT).
