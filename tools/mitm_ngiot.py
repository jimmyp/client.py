"""mitmproxy addon: capture Ecovacs ngiot endpoint/control + SST traffic.

Run:
    mitmdump -s tools/mitm_ngiot.py --listen-port 8080

Writes each relevant request/response pair as one JSON line to
ngiot_app_capture.jsonl in the cwd. We only keep the calls we care about so the
file stays readable: endpoint/control (the per-command apn + body) and the SST
issue. Everything else is ignored.
"""

from __future__ import annotations

import json
from typing import Any

from mitmproxy import http

OUTFILE = "ngiot_app_capture.jsonl"
KEEP = ("/api/iot/endpoint/control", "/api/iot/", "/sst/issue", "endpoint/control")


def _interesting(flow: http.HTTPFlow) -> bool:
    host = flow.request.pretty_host
    path = flow.request.path
    if "ecouser.net" not in host and "ecovacs" not in host:
        return False
    return any(k in path for k in KEEP) or "ngiot" in host


def _decode(b: bytes | None) -> Any:
    if not b:
        return None
    try:
        return json.loads(b)
    except Exception:
        try:
            return b.decode("utf-8", "replace")
        except Exception:
            return repr(b)


def response(flow: http.HTTPFlow) -> None:
    if not _interesting(flow):
        return
    rec = {
        "host": flow.request.pretty_host,
        "method": flow.request.method,
        "path": flow.request.path,
        "query": dict(flow.request.query),
        "req_headers": {
            k: v
            for k, v in flow.request.headers.items()
            if k.lower() in ("authorization", "x-eco-request-id", "content-type")
        },
        "req_body": _decode(flow.request.raw_content),
        "status": flow.response.status_code if flow.response else None,
        "resp_body": _decode(flow.response.raw_content) if flow.response else None,
    }
    line = json.dumps(rec, ensure_ascii=False)
    with open(OUTFILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    apn = rec["query"].get("apn")
    print(
        f"[ngiot] {rec['method']} {rec['path'][:40]} apn={apn} -> {rec['status']}",
        flush=True,
    )
