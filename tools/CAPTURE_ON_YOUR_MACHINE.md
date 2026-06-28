# Capturing q287s6 set-apns on your own machine

The sandboxed/headless rig couldn't reliably drive the app (offline under MITM, frida races,
blind taps). On **your** machine — full-size emulator window (or a real rooted phone), app
stays online, you tap precisely — capture just works. You drive; you paste me the payloads;
I implement them. This is the reliable path.

## What we need (4 surfaces, currently honest "not-supported" stubs)

For each, we need the `endpoint/control` **apn** and the request **body.data** the app sends:

| Capability | Tap in the app | Expected payload shape |
| --- | --- | --- |
| **volume** (set) | Settings → Volume slider, move it | `{"volume": N}` on some apn |
| **child lock** (set) | Settings → Child Lock toggle | `{"on": 0/1}` or `{"childLock": ...}` |
| **play sound / locate** | "Find robot" / locate button | likely `{}` or `{"sid": N}` |
| **life-span reset** | Maintenance → Reset a consumable | `{"type": "sideBrush"|...}` |

(Read side — battery, fan, water, volume, childLock, etc. — is already done; don't need it.)

## Setup (your machine, ~15 min, one time)

You need: Android Studio emulator (a **Google APIs**, *non*-Play-Store, arm64 image so you can
`adb root`) OR a rooted phone, plus mitmproxy and Frida. The proven recipe:

```bash
pip install mitmproxy frida-tools           # host
# Emulator: create a Google-APIs (not playstore) AVD, then:
emulator -avd <name> -writable-system -gpu host    # -gpu host is fine on YOUR machine
adb root && adb shell setenforce 0
# push matching frida-server (arm64, version = `frida --version`) to /data/local/tmp, chmod +x, run it
```

Install the official **ECOVACS HOME** app (pull from your phone via `adb pull`, or Play Store on
a play image). Install the mitmproxy CA into the **system** store (writable-system image):
```bash
# convert + push (hashed name), then reboot
HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
adb push ~/.mitmproxy/mitmproxy-ca-cert.pem /system/etc/security/cacerts/$HASH.0
adb shell chmod 644 /system/etc/security/cacerts/$HASH.0 && adb reboot
```

## Capture (the actual run)

1. Start the capture (uses the addon already in this repo):
   ```bash
   cd <repo>
   mitmdump -s tools/mitm_ngiot.py --listen-port 8080
   ```
   Point the emulator/phone proxy at your host:8080.

2. **Frida-unpin the app** so its TLS is interceptable. Use the httptoolkit
   frida-interception-and-unpinning scripts, JAVA-ONLY set (native hooks crash this app),
   and **spawn-mode** to beat the load race (this is what finally worked):
   ```bash
   frida -U -f com.eco.global.app \
     -l config.js \
     -l android/android-proxy-override.js \
     -l android/android-system-certificate-injection.js \
     -l android/android-certificate-unpinning.js \
     -l android/android-disable-root-detection.js
   ```
   (Set `CERT_PEM`, `PROXY_HOST`=host IP, `PROXY_PORT`=8080 in config.js.)
   If the app shows "offline": add the failing auth/analytics hosts to mitmproxy
   `--ignore-hosts` so they pass through natively (we hit: `users-base`,
   `api-app.ww.ecouser.net`, `bigdata-northamerica`, `sa-*-datasink`).

3. In the app, open your robot → tap each of the 4 things in the table above.

4. Pull the captured calls:
   ```bash
   python3 - <<'PY'
   import json
   for l in open("ngiot_app_capture.jsonl"):
       r=json.loads(l)
       if "endpoint/control" not in r.get("path",""): continue
       q=r["query"]; d=(r.get("req_body") or {}).get("body",{}).get("data")
       if isinstance(d,dict) and "fields" not in d and d:
           print("apn=%s  %s" % (q.get("apn"), json.dumps(d)))
   PY
   ```

## Hand it to me

Paste the `apn=... {payload}` lines for any of the 4 (even just one). I'll then, per the
`implementing-ngiot-deebot-commands` skill: write the real `NgiotSetCommand`/`NgiotExecuteCommand`,
add a wire-contract test pinning the exact apn+payload, mutation-check it, wire it into
`hardware/q287s6.py` (replacing the stub), and you live-verify. No guessing — only captured values.

Refs: DeebotUniverse/client.py#1569, #1642. See tools/NGIOT_FINDINGS.md for the full rig recipe.
