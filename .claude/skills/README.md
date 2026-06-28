# Skills

Reusable techniques distilled from adding ngiot support for the DEEBOT NEO 2.0
PLUS (`q287s6`). Each was baseline-tested (an agent attempting the task *without*
the skill got it wrong in specific, documented ways), then written to close
exactly those gaps. They're modular — use whichever stage you're at:

| Skill | Use when |
| --- | --- |
| [frida-mitm-pinned-android-app](frida-mitm-pinned-android-app/SKILL.md) | You need to read the HTTPS of a cert-pinned Android app via an emulator + Frida. |
| [capturing-ecovacs-ngiot-protocol](capturing-ecovacs-ngiot-protocol/SKILL.md) | A newer Ecovacs/Deebot device returns `code:0/data:null` and you need its real protocol. |
| [implementing-ngiot-deebot-commands](implementing-ngiot-deebot-commands/SKILL.md) | Turning a captured ngiot surface into deebot-client commands + wire-contract tests. |

The scripts and findings these are built on live in
[`tools/ngiot-reverse-engineering/`](../../tools/ngiot-reverse-engineering/).

Refs: DeebotUniverse/client.py#1569 (ngiot transport groundwork),
DeebotUniverse/client.py#1642 (q287s6 request).
