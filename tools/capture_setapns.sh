#!/usr/bin/env bash
# One-shot q287s6 set-apn capture — run on YOUR host (full GPU, visible window).
#
# Boots the existing `ngiot` AVD, restores root/permissive, starts frida-server +
# mitmproxy (with the offline-fix host passthrough), spawn-launches the Ecovacs app
# under the Java-only unpinning scripts (spawn-mode beats the H5 load race), then
# tails the capture and prints every endpoint/control WRITE (apn + body.data) as you
# tap. Tap: volume slider, child-lock toggle, find-robot/play-sound, lifespan reset.
# Ctrl-C when done, then paste the printed "apn=... {...}" lines into the issue.
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

say "1/6 boot emulator (visible window)"
if ! adb devices | grep -q "$S"; then
  # Tuned for a fast host: more cores/RAM, no audio/snapshot overhead, full
  # network speed + no simulated latency. GPU=swiftshader_indirect (software):
  # slower than -gpu host but STABLE — host GPU crashed rendering the H5 control
  # screen (Vulkan/Chromium context loss). Override with EMU_GPU=host to retry.
  "$ANDROID_HOME/emulator/emulator" -avd "$AVD" -writable-system \
    -gpu "${EMU_GPU:-swiftshader_indirect}" -cores 6 -memory 6144 \
    -no-boot-anim -no-audio -no-snapshot \
    -netspeed full -netdelay none \
    >/tmp/emu.log 2>&1 &
fi
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; do sleep 2; done
echo "booted."

say "1a/6 force wifi/data ON (AVD can persist wifi-off from a prior airplane toggle"
# -> 'Network is unreachable' / wlan0 DOWN / no IP. Re-enabling brings wlan0 up.
adb shell svc wifi enable >/dev/null 2>&1
adb shell svc data enable >/dev/null 2>&1
sleep 5

say "1b/6 wait for network to actually validate (not just boot)"
# The app times out if it fires requests before connectivity is VALIDATED.
# Wait for a validated default network (public DNS reachable), up to ~60s.
for i in $(seq 1 30); do
  if adb shell dumpsys connectivity 2>/dev/null | grep -q "VALIDATED"; then echo "network validated."; break; fi
  sleep 2
done
# Pin a reliable public DNS in the guest (cuts DNS-hiccup timeouts)
adb root >/dev/null 2>&1; sleep 1
adb shell "setprop net.dns1 8.8.8.8; setprop net.dns2 1.1.1.1" >/dev/null 2>&1 || true

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

say "5/6 spawn app under frida unpinning + watchdog (survives app restarts)"
# The app RESTARTS when you enter the H5 control screen, which kills a plain
# spawn-mode frida (and its endpoint/control calls then fail TLS, capturing
# nothing). So: spawn once to seed hooks at launch, then a watchdog re-attaches
# on every pid change so unpinning is ALWAYS live when you tap controls.
FRIDA_SCRIPTS=(-l "$UNPIN/config.js"
  -l "$UNPIN/android/android-proxy-override.js"
  -l "$UNPIN/android/android-system-certificate-injection.js"
  -l "$UNPIN/android/android-certificate-unpinning.js"
  -l "$UNPIN/android/android-disable-root-detection.js")

adb shell am force-stop "$PKG" 2>/dev/null; sleep 1
nohup frida -U -f "$PKG" "${FRIDA_SCRIPTS[@]}" >/tmp/frida.out 2>&1 &
sleep 14
grep -q "unpinning completed" /tmp/frida.out && echo "spawn unpinning active." \
  || echo "WARN: spawn unpinning not confirmed — check /tmp/frida.out"

# watchdog: re-attach whenever the app pid changes (i.e. after a restart)
watchdog(){
  local last=""
  while true; do
    adb shell pidof frida-server >/dev/null 2>&1 || { adb root >/dev/null 2>&1; sleep 1; adb shell setenforce 0 >/dev/null 2>&1; adb shell "nohup /data/local/tmp/frida-server >/dev/null 2>&1 &"; sleep 2; }
    local pid; pid=$(adb shell pidof "$PKG" 2>/dev/null | tr -d '\r')
    if [ -n "$pid" ] && [ "$pid" != "$last" ]; then
      pkill -f "frida -U -p" 2>/dev/null; sleep 1
      nohup frida -U -p "$pid" "${FRIDA_SCRIPTS[@]}" >/tmp/frida_wd.out 2>&1 &
      sleep 8
      grep -q "unpinning completed" /tmp/frida_wd.out 2>/dev/null && { echo "[watchdog] re-attached pid $pid"; last="$pid"; }
    fi
    sleep 3
  done
}
watchdog & WD_PID=$!
trap 'kill $WD_PID 2>/dev/null; pkill -f "frida -U" 2>/dev/null' EXIT
echo "watchdog running (auto-reattaches on app restart)."

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
