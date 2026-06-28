#!/usr/bin/env bash
# One-shot q287s6 set-apn capture — run on YOUR host (full GPU, visible window).
#
# Boots the existing `ngiot` AVD, restores root/permissive, starts frida-server +
# mitmproxy (with the offline-fix host passthrough), spawn-launches the Ecovacs app
# under the Java-only unpinning scripts (spawn-mode beats the H5 load race), then
# tails the capture and prints every endpoint/control WRITE (apn + body.data) as you
# tap. Tap: volume slider, child-lock toggle, find-robot/play-sound, lifespan reset.
# Ctrl-C when done, then paste the printed "apn=... {...}" lines back to Claude.
#
# Everything it needs is already on this machine (AVD, frida-server, unpin scripts,
# APK, mitm CA). It only orchestrates — installs nothing.
set -uo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
AVD="${AVD:-ngiot}"
PKG="com.eco.global.app"
PORT=8080
ADDON="$(cd "$(dirname "$0")" && pwd)/mitm_ngiot.py"
CAP="$(cd "$(dirname "$0")/.." && pwd)/ngiot_app_capture.jsonl"
UNPIN=/tmp/frida-interception-and-unpinning
VENV=/tmp/capvenv
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
S=emulator-5554

say(){ printf '\n=== %s ===\n' "$*"; }

say "1/6 boot emulator (visible window, host GPU)"
if ! adb devices | grep -q "$S"; then
  "$ANDROID_HOME/emulator/emulator" -avd "$AVD" -writable-system -gpu host -no-boot-anim >/tmp/emu.log 2>&1 &
fi
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; do sleep 2; done
echo "booted."

say "2/6 root + permissive (required for frida to attach)"
adb root >/dev/null 2>&1; sleep 2; adb wait-for-device
adb shell setenforce 0 >/dev/null 2>&1
echo "selinux: $(adb shell getenforce | tr -d '\r')  id: $(adb shell id | tr -d '\r' | grep -o 'uid=[^ ]*')"

say "3/6 frida-server"
adb shell pidof frida-server >/dev/null 2>&1 || { adb shell "nohup /data/local/tmp/frida-server >/dev/null 2>&1 &"; sleep 3; }
echo "frida-server pid: $(adb shell pidof frida-server | tr -d '\r')"

say "4/6 mitmproxy (offline-fix: pass through auth/analytics hosts that fail TLS)"
pkill -f "mitmdump.*$PORT" 2>/dev/null; sleep 1
: > "$CAP"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
IGNORE='users-base\.|bigdata-northamerica\.|sa-us-datasink\.|sa-eu-datasink\.|api-app\.ww\.ecouser\.net'
nohup mitmdump -s "$ADDON" --listen-port "$PORT" --ignore-hosts "$IGNORE" \
  --set console_eventlog_verbosity=warn >/tmp/mitm.out 2>&1 &
sleep 4
adb shell settings delete global http_proxy >/dev/null 2>&1   # frida proxies in-process
adb shell wm size 1080x1920 >/dev/null 2>&1; adb shell wm density 440 >/dev/null 2>&1
echo "mitm listeners: $(lsof -iTCP:$PORT -sTCP:LISTEN 2>/dev/null | grep -c mitmdump)"

say "5/6 spawn app under frida unpinning (Java-only; spawn-mode beats the load race)"
adb shell am force-stop "$PKG" 2>/dev/null; sleep 1
nohup frida -U -f "$PKG" \
  -l "$UNPIN/config.js" \
  -l "$UNPIN/android/android-proxy-override.js" \
  -l "$UNPIN/android/android-system-certificate-injection.js" \
  -l "$UNPIN/android/android-certificate-unpinning.js" \
  -l "$UNPIN/android/android-disable-root-detection.js" >/tmp/frida.out 2>&1 &
sleep 14
if grep -q "unpinning completed" /tmp/frida.out; then echo "unpinning active."; else
  echo "WARN: unpinning not confirmed — check /tmp/frida.out"; fi

say "6/6 CAPTURING — now drive the app, then Ctrl-C"
cat <<'TIP'
In the app (it should be ONLINE; if 'offline', back out + reopen the device once):
  open robot -> Suction (change it: confirms capture works) -> Water ->
  gear/Settings: Volume, Child Lock, Voice/Sound -> Find Robot/locate ->
  Maintenance: Reset a consumable.   AVOID the "Me" tab (logs out) and "Start" (moves bot).
Each control WRITE prints below as:  apn=NNNNN  {payload}
TIP
tail -n0 -f "$CAP" | python3 -u -c '
import sys, json
for line in sys.stdin:
    try: r = json.loads(line)
    except Exception: continue
    if "endpoint/control" not in r.get("path",""): continue
    q = r.get("query", {}); d = (r.get("req_body") or {}).get("body",{}).get("data")
    if isinstance(d, dict) and "fields" not in d and d:
        print("apn=%s  %s" % (q.get("apn"), json.dumps(d)), flush=True)
'
