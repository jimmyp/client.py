# q287s6 set-apn capture rig — setup recipe & known blockers

This is the repeatable recipe for capturing the 4 still-unmapped q287s6 ngiot **set-apns**
(volume / play-sound / child-lock / lifespan-reset). The read + control surfaces are already
mapped headlessly via [`ngiot_capability_loop.py`](ngiot_capability_loop.py) (apn=10001 oracle) —
**this rig is only needed for the SET writes the app emits.**

> ⚠️ **As of 2026-06-29 the Android emulator rig does NOT work on this Mac.** A truly clean cold
> boot (`-wipe-data`, snapshot deleted, stock networking) reproducibly comes up with **no default
> route** on either `eth0` (10.0.2.15) or `wlan0` (10.0.2.16) — only the local-subnet routes — so
> the guest has zero internet egress and the app can't get online. `ip route add default` is
> permission-blocked even as root. **Recommended path is a physical rooted phone** (see bottom).
> The recipe below is the *intended* flow, kept for when the emulator egress is fixed or on a
> different host where it works (it DID work on 2026-06-28).

---

## 0. What the rig is

```
[Ecovacs app in emulator] --TLS--> [frida unpinning] --> [mitmproxy on host loopback] --> internet
                                         ^                        |
                                  (defeats cert pinning)   (logs apn + body for each control write)
```

- **frida** (root, SELinux permissive) injects httptoolkit's Java-only unpinning scripts so the
  app's pinned TLS can be read by mitmproxy. **Native hooks SIGSEGV the app — Java scripts only.**
- **mitmproxy** records every `endpoint/control` POST; the capture tail prints `apn=NNNNN {payload}`
  for each WRITE (reads use `body.data={fields:[...]}` and are filtered out).
- You tap the real control in the app; the wire payload is what we encode into the command class.

## 1. Prerequisites (all already present on this machine as of 2026-06-29)

| Thing | Location / check |
|---|---|
| AVD `ngiot` | `~/.android/avd/ngiot.avd` — Android 14, google_apis, arm64 |
| Ecovacs app | pkg `com.eco.global.app` (reinstall after `-wipe-data`) |
| frida-server | pushed at `/data/local/tmp/frida-server` (v17.15.3) |
| frida CLI + mitmproxy | rebuild venv: `uv venv /tmp/capvenv && source /tmp/capvenv/bin/activate && uv pip install "frida==<server-ver>" frida-tools mitmproxy` (**CLI version MUST match frida-server**) |
| httptoolkit unpin scripts | `/tmp/frida-interception-and-unpinning/` |
| host mitm CA | `~/.mitmproxy/mitmproxy-ca-cert.pem` |
| capture script | [`capture_setapns.sh`](capture_setapns.sh) (orchestrates all of the below) |
| mitm addon | [`mitm_ngiot.py`](mitm_ngiot.py) |

## 2. Boot the emulator (cold, current network)

```bash
ANDROID_HOME="$HOME/Library/Android/sdk"
"$ANDROID_HOME/emulator/emulator" -avd ngiot -writable-system \
  -gpu swiftshader_indirect -cores 6 -memory 6144 \
  -no-boot-anim -no-audio -no-snapshot \
  -netspeed full -netdelay none &
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = 1 ]; do sleep 2; done
```

- `-gpu swiftshader_indirect` (software): STABLE. `-gpu host` crashes rendering the app's H5
  control screen (Vulkan context loss). Do not use host GPU.
- **VERIFY EGRESS FIRST, before anything else:**
  ```bash
  adb shell "curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    http://connectivitycheck.gstatic.com/generate_204"   # want: 204
  ```
  If this is **empty**, STOP — the network is broken (the 2026-06-29 blocker). No point proceeding;
  the app will be offline. Diagnose the default route: `adb shell ip route show` — if there's no
  `default via ...` line, egress is dead. See "Known blockers" below.

## 3. Special permissions / app access setup (the bits that need root)

These are what make the rig able to see inside the app. The `capture_setapns.sh` script does them,
but here they are explicitly so you understand each "special permission":

```bash
adb root                 # restart adbd as root (REQUIRED for frida to ptrace-attach the app)
adb shell setenforce 0   # SELinux PERMISSIVE (REQUIRED: enforcing blocks frida injection)
# frida-server must run as root:
adb shell pidof frida-server || adb shell "nohup /data/local/tmp/frida-server >/dev/null 2>&1 &"
# Install the mitmproxy CA so the app's TLS validates THROUGH the proxy:
#   - frida's android-system-certificate-injection.js injects it at runtime (preferred), AND/OR
#   - push to system store: remount /system rw, copy mitm CA as <hash>.0 to
#     /system/etc/security/cacerts/, reboot. (Needs -writable-system at boot.)
# NOTE: installing a CA into the system store does NOT fix the app's MQTT presence connection —
#   that uses the app's OWN bundled ECOVACS CA via Paho/Aliyun LinkKit, not the Android store.
#   (This is also why deebot-client itself bundles the ECOVACS CA — see deebot_client/certs/.)
```

Permission summary — each is load-bearing:
- **`adb root`** → frida can attach to the app process.
- **`setenforce 0`** → SELinux won't kill the injection.
- **`-writable-system`** (boot flag) → lets you push a CA into the system store.
- **mitm CA trusted** → app's HTTPS to api-ngiot validates through mitmproxy so we can read it.
- **spawn-mode frida (`frida -f`)** → hooks are live BEFORE the H5 control screen loads (beats the
  race where the app restarts on opening the device and fires `endpoint/control` before re-attach).

## 4. Start proxy + spawn the app under frida (use the script)

```bash
source /tmp/capvenv/bin/activate
./tools/capture_setapns.sh        # boots, roots, starts frida-server + mitmproxy, spawn-launches
                                  # the app under unpinning + a watchdog, tails the WRITE capture
```

The script ends in a live tail. Each control WRITE prints as `apn=NNNNN  {payload}`.

## 5. What to tap (you do the taps — emulator blind-taps are unreliable)

With the robot **ONLINE** in the app, open the robot, then for each:
- **Volume** — drag the volume slider in settings
- **Play sound / find robot** — tap locate / play-sound
- **Child lock** — toggle child lock
- **Lifespan reset** — Maintenance → reset a consumable (brush/filter)

⚠️ **AVOID** the "Me" tab (logs you out) and **"Start"** (moves the vacuum — only if explicitly OK'd).

Paste the printed `apn=... {...}` lines back; they get encoded into the ngiot command classes
(see [`implementing-ngiot-deebot-commands`] skill + `deebot_client/commands/ngiot/`).

---

## Known blockers (ruled out / confirmed dead — do NOT re-chase these)

Confirmed across multiple sessions (see memory `q287s6-capture-lessons`):

1. **No guest egress / no default route (2026-06-29, current):** clean cold boot → `eth0`+`wlan0`
   get IPs but NO `default via` route; all `curl` empty; `ip route add` permission-denied even as
   root. NOT caused by: WiFi switching (fresh boots fail identically), VPN (none configured; raw
   LAN TCP works), netsim VirtioWifi (disabling it didn't help), or stale snapshot (deleting the
   3.9G `default_boot` + `-wipe-data` didn't help). It's the emulator build's networking on this
   host. **No adb-level fix found.**
2. **vmnet won't engage:** `-vmnet-shared` needs the restricted entitlement
   `com.apple.vm.networking`; the emulator's qemu binary lacks it; ad-hoc re-signing CANNOT carry a
   restricted entitlement (Gatekeeper rejects it, no provisioning profile). Needs a paid Apple Dev
   cert provisioned by Apple. Not worth it for a throwaway rig.
3. **App offline under MITM** (when egress DID work): auth hosts on a non-OkHttp stack fail TLS via
   the proxy; pass them through (`--ignore-hosts` for users-base, api-app.ww, datasink, bigdata).
4. **frida drops on app restart:** opening the control screen restarts the app; use spawn-mode +
   watchdog (in the script) so unpinning is always live.
5. **GPU host crashes:** use `swiftshader_indirect`.
6. **Blind taps land wrong** on the scaled window (uiautomator can't see WebView nodes) — once hit
   "Start" and moved the physical vacuum. Human does the taps.

## Recommended path: physical rooted Android phone

The app + its bundled ECOVACS CA + MQTT presence all work normally on a real phone, taps are
precise, and the network survives moving around (it's a phone). Root it, run the app, and proxy
ONLY the REST path (`api-ngiot.dc-*.ww.ecouser.net`) through mitmproxy + frida unpinning — leave
the MQTT presence connection direct. This sidesteps every blocker above.
