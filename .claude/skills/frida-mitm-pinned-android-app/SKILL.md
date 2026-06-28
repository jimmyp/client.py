---
name: frida-mitm-pinned-android-app
description: Use when you need to intercept and read the HTTPS traffic of a modern Android app that uses certificate pinning (TLS handshake fails in mitmproxy, app ignores the proxy CA), on an Android emulator on an Apple Silicon Mac.
---

# MITM a pinned Android app (emulator + Frida)

## Overview

A modern Android app won't trust a mitmproxy CA you add as a *user* cert
(Android 7+), and if it pins it won't trust a *system* cert either. To read its
HTTPS you need: a **rootable emulator**, the mitmproxy CA in the **system**
store, and **Frida** to defeat pinning at runtime. The httptoolkit
`frida-interception-and-unpinning` scripts also inject the CA in-process, so a
locked `/system` is not actually a blocker.

## The hard-won gotchas (these are what bite)

These are the things a from-scratch attempt gets wrong — they cost hours:

- **Use a `google_apis` (NON-Play) arm64 image.** Play-store images can't
  `adb root`. Match the emulator arch (arm64 on Apple Silicon) for `frida-server`.
- **Boot with `-gpu swiftshader_indirect` (software GL).** Host GL on Apple
  Silicon hangs/crashes the emulator mid-session (`QEMU2 main loop` no response,
  `Failed to find ColorBuffer`). Software GL is far more stable.
- **`avdmanager` "Package path is not valid / null"**: it computes the SDK root
  from its own location. With the Homebrew cask, *copy* (don't symlink)
  cmdline-tools into `$ANDROID_HOME/cmdline-tools/latest/` and run it from there.
- **Use JDK 17, not 21+/26.** Newer JDKs make `avdmanager` print only `null`.
- **`frida -f` (spawn) fails "need Gadget to attach on jailed Android".** On the
  AVD, spawn-gating is broken. Launch the app first, then **attach by PID**
  (`frida -U -p <pid>`). Wait for a *stable* pid (same value twice) before
  attaching — early splash pids die.
- **Native hooks can SIGSEGV the app.** Some apps (Ecovacs v3.13) crash when the
  bundle's `native-connect-hook.js` / `native-tls-hook.js` load. Use the
  **Java-only** subset (config + proxy-override + system-certificate-injection +
  certificate-unpinning + disable-root-detection). Bisect by adding scripts one
  at a time if it crashes.
- **The control UI may be an H5/WebView** (`H5RobotActivity`). `uiautomator`
  can't see web buttons and coordinate-taps are guesswork — a human has to tap,
  or you drive the underlying API directly.
- **Set the emulator display sane.** The AVD can boot at 320x640; `adb shell wm
  size 1080x1920 && wm density 440` so the app lays out.

## Workflow (ordered)

```
google_apis arm64 AVD  ->  boot -writable-system -gpu swiftshader_indirect
  ->  adb root; setenforce 0; push+run frida-server (arch-matched)
  ->  install mitmproxy CA into /system/etc/security/cacerts (hashed .0 name)
  ->  mitmdump (capture addon); clear global http_proxy (Frida proxies in-proc)
  ->  launch app; wait for STABLE pid; frida -U -p <pid> -l <java-only scripts>
  ->  drive the app; read decrypted traffic
```

System-cert install (do it once; persists in the AVD):
```bash
hash=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
cp ~/.mitmproxy/mitmproxy-ca-cert.pem /tmp/$hash.0
adb root && adb remount
adb push /tmp/$hash.0 /system/etc/security/cacerts/$hash.0
adb shell chmod 644 /system/etc/security/cacerts/$hash.0
```

Unpinning (Java-only, attach mode) using
[httptoolkit/frida-interception-and-unpinning](https://github.com/httptoolkit/frida-interception-and-unpinning)
— set `CERT_PEM`/`PROXY_HOST=10.0.2.2`/`PROXY_PORT` in `config.js` first:
```bash
frida -U -p <pid> \
  -l ./config.js \
  -l ./android/android-proxy-override.js \
  -l ./android/android-system-certificate-injection.js \
  -l ./android/android-certificate-unpinning.js \
  -l ./android/android-disable-root-detection.js
```

## Verifying it works

Success = the app's own requests to its API hosts show up *decrypted* in
mitmproxy (not "Client TLS handshake failed"). A quick proof: load any HTTPS
site in the emulator browser first (confirms proxy + CA), then launch the app
and watch its API host appear in the flow.

## Common mistakes

| Mistake | Reality |
| --- | --- |
| User-cert install | Android 7+ apps ignore user CAs. System store. |
| Play-store image | Can't `adb root`. Use `google_apis`. |
| `frida -f` spawn | Fails "jailed Android" on the AVD. Attach by pid. |
| Full unpinning bundle | Native hooks crash some apps. Java-only subset. |
| Host GPU | Emulator hangs on Apple Silicon. `swiftshader_indirect`. |
| `uiautomator` taps on the controls | They may be a WebView. Human taps / drive the API. |
| "handshake failed" everywhere | Cert not in *system* store, or pinning not bypassed. |

A full bring-up recipe (exact commands, AVD already built) lives in
`tools/ngiot-reverse-engineering/findings/FINDINGS.md`.
