# q287s6 reverse-engineering tools

Working notes and capture scripts used to bring up the DEEBOT NEO 2.0 PLUS
(`q287s6`). Fork-only: this directory is not part of any upstream PR.

Scripts that talk to a real device need `ECOVACS_USERNAME`, `ECOVACS_PASSWORD`
and `ECOVACS_COUNTRY` in the environment. `ngiot_capture_live.py` and
`ngiot_capture_wild.py` disable TLS verification and are kept for reference only.
`mitm_ngiot.py` writes bearer tokens to `ngiot_app_capture.jsonl`; delete that
file after use.
