#!/usr/bin/env python3
"""Capture the H5 control WebView's network traffic via Chrome DevTools Protocol.

The q287s6 H5 control screen (com.ecovacs.h5_bridge_v2) gets live robot state
through the WebView's own Chromium network stack (JS fetch/XHR/WebSocket), which
is invisible to frida Java/OkHttp hooks. After forcing
setWebContentsDebuggingEnabled(true) (see tools/wv_debug.js) and
`adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>`, this connects
to the page's CDP WebSocket, enables the Network domain, and logs every request,
response, and -- crucially -- WebSocket frame, so we can see how device state
actually reaches the app. Redacts obvious token query params/headers.

Usage:
  python tools/cdp_h5_capture.py            # uses ws from /json, runs until Ctrl-C
"""

from __future__ import annotations

import json
import sys
import time
from urllib.request import urlopen

import websocket  # type: ignore[import-untyped]

_CDP = "http://127.0.0.1:9222/json"
_REDACT_KEYS = ("token", "sign", "secret", "auth", "iottoken", "password")


def _redact(s: str | None) -> str | None:
    if not s:
        return s
    out = s
    for k in _REDACT_KEYS:
        # crude: blank out value after key= up to & or end
        import re

        out = re.sub(
            rf"({k}=)[^&\s\"]+", r"\1<REDACTED>", out, flags=re.IGNORECASE
        )
    return out


def main() -> int:
    pages = json.load(urlopen(_CDP))
    page = next((p for p in pages if p.get("webSocketDebuggerUrl")), None)
    if not page:
        print("no debuggable page found", file=sys.stderr)
        return 1
    ws_url = page["webSocketDebuggerUrl"]
    print(f"# attaching CDP to: {page.get('title')} {page.get('url', '')[:60]}")

    # Newer Chromium rejects the CDP WebSocket unless the Origin is allowed.
    # Sending no Origin header (suppress_origin) sidesteps the 403.
    ws = websocket.create_connection(ws_url, max_size=None, suppress_origin=True)
    mid = 0

    def send(method: str, params: dict | None = None) -> None:
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))

    # Enable the domains we care about.
    send("Network.enable")
    send("Page.enable")
    print("# Network domain enabled; logging requests + websocket frames. Ctrl-C to stop.")

    ws.settimeout(1.0)
    while True:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except KeyboardInterrupt:
            break
        except Exception:
            break
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        m = msg.get("method")
        p = msg.get("params", {})

        if m == "Network.requestWillBeSent":
            req = p.get("request", {})
            print(json.dumps({
                "ev": "request",
                "method": req.get("method"),
                "url": _redact(req.get("url")),
            }))
        elif m == "Network.responseReceived":
            r = p.get("response", {})
            print(json.dumps({
                "ev": "response",
                "status": r.get("status"),
                "url": _redact(r.get("url")),
                "mime": r.get("mimeType"),
            }))
        elif m == "Network.webSocketCreated":
            print(json.dumps({"ev": "ws_created", "url": _redact(p.get("url"))}))
        elif m == "Network.webSocketFrameReceived":
            payload = p.get("response", {}).get("payloadData", "")
            print(json.dumps({"ev": "ws_recv", "data": payload[:1000]}))
        elif m == "Network.webSocketFrameSent":
            payload = p.get("response", {}).get("payloadData", "")
            print(json.dumps({"ev": "ws_sent", "data": _redact(payload[:1000])}))

    ws.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
