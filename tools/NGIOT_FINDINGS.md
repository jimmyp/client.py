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

> **Host note for PR #1569:** the maintainer's code derives the control host as
> `api-base.dc-<region>.ww.ecouser.net`, but that host returns **HTTP 404
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

## Bring the capture/test rig back up (for a follow-up session)

The Android emulator AVD `ngiot` persists at `~/.android/avd/ngiot.avd` (its userdata
holds the v3.13.0 Ecovacs app install + the mitmproxy system CA). Tooling under `/tmp`
(frida-server, app split APKs, unpinning scripts, capvenv, the `*.0` system cert) may be
cleared on a Mac reboot — re-fetch if missing (see this file's history / commit messages).

```bash
export ANDROID_HOME=$HOME/Library/Android/sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME ANDROID_AVD_HOME=$HOME/.android/avd
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

# 1. Boot emulator (software GL is far more stable on Apple Silicon than host GL)
"$ANDROID_HOME/emulator/emulator" -avd ngiot -writable-system -no-snapshot \
  -no-boot-anim -gpu swiftshader_indirect &
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = 1 ]; do sleep 2; done

# 2. Root + permissive + start frida-server (binary at /data/local/tmp/frida-server;
#    re-push /tmp/frida-server if the device lost it)
adb root; sleep 2; adb shell setenforce 0
adb shell "nohup /data/local/tmp/frida-server >/dev/null 2>&1 &"; sleep 3

# 3. mitmproxy with the ngiot capture addon (CA already in the AVD's system store)
cd /Users/jim/code/client.py && source /tmp/capvenv/bin/activate
nohup mitmdump -s tools/mitm_ngiot.py --listen-port 8080 \
  --set console_eventlog_verbosity=warn >/tmp/mitm.out 2>&1 &
adb shell settings delete global http_proxy   # frida scripts proxy in-process; don't double up

# 4. Set a sane phone display (the AVD boots tiny: 320x640)
adb shell wm size 1080x1920; adb shell wm density 440

# 5. Launch app, then ATTACH (spawn -f fails "jailed Android" on this AVD; native hooks
#    SIGSEGV this app -> JAVA-ONLY scripts). Re-install splits from /tmp/ecovacs313 if gone.
adb shell am start -n com.eco.global.app/com.eco.main.activity.EcoLauncherActivity; sleep 6
PID=$(adb shell pidof com.eco.global.app | tr -d '\r')
cd /tmp/frida-interception-and-unpinning && frida -U -p "$PID" \
  -l ./config.js -l ./android/android-proxy-override.js \
  -l ./android/android-system-certificate-injection.js \
  -l ./android/android-certificate-unpinning.js \
  -l ./android/android-disable-root-detection.js
# Drive the app; ngiot endpoint/control calls land in ngiot_app_capture.jsonl (gitignored).
```

For a pure transport/auth round-trip without the app/emulator, use
`tools/ngiot_endpoint_probe.py` with `~/.ecovacs.env` sourced.
