#!/usr/bin/env python3
"""Decode the raw MQTT bytes captured by tools/frida_mqtt_capture.js.

The frida script taps SSL_read/SSL_write and emits the plaintext MQTT packets
that Paho exchanges with the jmq broker (which bypasses mitmproxy). This parses
the MQTT 3.1.1 wire format into readable CONNECT / SUBSCRIBE / PUBLISH records
and REDACTS credentials (the CONNECT password, and anything token-shaped) so the
output is safe to paste into the protocol doc.

Input: lines of the frida `send()` JSON, one per packet, on stdin or a file:
  {"dir": "tx", "type": "CONNECT", "len": 123, "hex": "10..."}

Usage:
  frida -U -f com.eco.global.app -l tools/frida_mqtt_capture.js -o /tmp/mqtt.log
  # ... drive the app, Ctrl-C ...
  python tools/decode_mqtt_capture.py /tmp/mqtt.log

This is a capture/diagnostic helper, not shipped library code.
"""

from __future__ import annotations

import json
import sys
from typing import Any

_REDACT = "<REDACTED>"
_TYPES = {
    1: "CONNECT",
    2: "CONNACK",
    3: "PUBLISH",
    8: "SUBSCRIBE",
    9: "SUBACK",
}


def _read_remaining_length(data: bytes, i: int) -> tuple[int, int]:
    """MQTT variable-length int. Returns (value, next_index)."""
    mult = 1
    value = 0
    while True:
        byte = data[i]
        i += 1
        value += (byte & 0x7F) * mult
        if (byte & 0x80) == 0:
            break
        mult *= 128
    return value, i


def _read_str(data: bytes, i: int) -> tuple[str, int]:
    n = (data[i] << 8) | data[i + 1]
    i += 2
    s = data[i : i + n].decode("utf-8", "replace")
    return s, i + n


def _decode_connect(body: bytes) -> dict[str, Any]:
    i = 0
    proto, i = _read_str(body, i)
    level = body[i]
    flags = body[i + 1]
    i += 2
    keepalive = (body[i] << 8) | body[i + 1]
    i += 2
    out: dict[str, Any] = {
        "protocol": proto,
        "level": level,
        "clean_session": bool(flags & 0x02),
        "keepalive": keepalive,
    }
    # MQTT 5 has a properties block after keepalive; level 5 == 0x05
    if level >= 5:
        plen, i = _read_remaining_length(body, i)
        i += plen  # skip properties (not needed for our purposes)
    client_id, i = _read_str(body, i)
    out["client_id"] = client_id
    if flags & 0x04:  # will flag
        _, i = _read_str(body, i)  # will topic
        _, i = _read_str(body, i)  # will message
    if flags & 0x80:  # username
        username, i = _read_str(body, i)
        out["username"] = username
    if flags & 0x40:  # password
        password, i = _read_str(body, i)
        out["password"] = _REDACT + f" (len={len(password)})"
    return out


def _decode_subscribe(body: bytes) -> dict[str, Any]:
    i = 2  # packet identifier
    topics = []
    while i < len(body):
        topic, i = _read_str(body, i)
        qos = body[i]
        i += 1
        topics.append({"topic": topic, "qos": qos})
    return {"topics": topics}


def _decode_publish(first_byte: int, body: bytes) -> dict[str, Any]:
    qos = (first_byte >> 1) & 0x03
    i = 0
    topic, i = _read_str(body, i)
    if qos > 0:
        i += 2  # packet identifier
    payload = body[i:]
    try:
        decoded: Any = json.loads(payload)
    except Exception:
        decoded = payload.decode("utf-8", "replace")
    return {"topic": topic, "qos": qos, "payload": decoded}


def decode_packet(rec: dict[str, Any]) -> dict[str, Any] | None:
    data = bytes.fromhex(rec["hex"])
    if len(data) < 2:
        return None
    first = data[0]
    ptype = first >> 4
    name = _TYPES.get(ptype)
    if name is None:
        return None
    _, body_start = _read_remaining_length(data, 1)
    body = data[body_start:]
    out: dict[str, Any] = {"dir": rec.get("dir"), "packet": name}
    try:
        if name == "CONNECT":
            out.update(_decode_connect(body))
        elif name == "SUBSCRIBE":
            out.update(_decode_subscribe(body))
        elif name == "PUBLISH":
            out.update(_decode_publish(first, body))
    except Exception as exc:
        out["parse_error"] = repr(exc)
    return out


def main() -> int:
    source = open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin
    for line in source:
        line = line.strip()
        if not line:
            continue
        # accept either the raw frida send() json or a "MQTTCAP {...}" console line
        line = line.removeprefix("MQTTCAP ")
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if "hex" not in rec:
            continue
        decoded = decode_packet(rec)
        if decoded is not None:
            print(json.dumps(decoded, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
