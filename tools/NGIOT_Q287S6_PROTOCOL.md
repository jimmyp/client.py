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
RESP body.data: {"battery": 100, "breakCleanStatus": false, "chargeStatus": false, "childLock": false, "cleanArea": 0, "cleanCount": 1, "cleanLogReport": {"cid": "<redacted>", "resource": "<resource>"}, "cleanTime": 0, "cleanValues": null, "consumables": [{"left": 0, "total": 0, "type": "sideBrush"}, {"left": 0, "total": 0, "type": "rollBrush"}, {"left": 0, "total": 0, "type": "filter"}, {"left": 0, "total": 0, "type": "unitCare"}], "deviceInfo": {"fwVersion": "10.0.6", "ip": "<redacted-ip>", "mac": "<redacted-mac>", "mcuVersion": "<redacted>", "rssi": "xxx", "sn": "xxxxxx", "ssid": "xxx", "wkVersion": "0.0.9"}, "disturbSwitch": false, "disturbTimeSet": {}, "dormant": false, "error": [0], "fanMode": "strong", "isEurope": null, "mopState": "installed", "nextSchedule": null, "otaData": {"failedCode": 0, "otaInfo": {"progress": 100, "ver": ""}, "otaRst": 0, "otaStatus": "done"}, "pauseSwitch": false, "relocateSwitch": true, "silentOtaSwitch": true, "stationStatus": null, "stationType": null, "timeZone": 0, "unitSet": "squareMeter", "voiceData": {"downloads": [{"id": "", "md5": "", "name": "", "progress": 100, "size": 0, "status": "down"}], "id": "EN", "md5": "", "name": "English", "size": 100, "url": ""}, "waterMode": "low", "workMode": "auto"}
```

### apn=10001  [GET]
```
REQ body.data: {"fields": ["timeZone", "deviceTimer"]}
RESP body.data: <schedule list redacted>
```

### apn=30001  [GET]
```
REQ body.data: {"fields": ["mapStatus"]}
RESP body.data: {"mapStatus": "mappingDone"}
```

### apn=30001  [GET]
```
REQ body.data: {"fields": ["<map list field>"]}
RESP body.data: <map list redacted>
```

### apn=30001  [GET]
```
REQ body.data: {"mapId": "5", "fields": ["mapTraceData"]}
RESP body.data: <map data redacted>
```

### apn=30001  [GET]
```
REQ body.data: {"mapId": "5", "fields": ["virtualWalls", "mopWalls", "carpets"]}
RESP body.data: {"mapId": "5", "mopWalls": "", "virtualWalls": ""}
```

### apn=30001  [GET]
```
REQ body.data: {"mapId": "5", "fields": ["mapData", "areas", "pos"]}
RESP body.data: <map data redacted>
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
