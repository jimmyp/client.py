"""SST (short-lived service token) authentication for ngiot devices."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any

from aiohttp import ClientTimeout
import orjson

from .logging_filter import get_logger

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from .authentication import Authenticator
    from .models import ApiDeviceInfo

_LOGGER = get_logger(__name__)

SST_ISSUE_PATH = "/api/new-perm/token/sst/issue"
# token validity in seconds
SST_EXP_SECONDS = 600
# refresh before expiry
_SST_REFRESH_RATIO = 0.9
_TIMEOUT = ClientTimeout(60)


@dataclass(frozen=True)
class _CachedToken:
    token: str
    expires_at: float


class SstAuthenticator:
    """Mint and cache per-device SST tokens for the ngiot transport."""

    def __init__(self, authenticator: Authenticator, session: ClientSession) -> None:
        self._authenticator = authenticator
        self._session = session
        self._lock = asyncio.Lock()
        self._tokens: dict[str, _CachedToken] = {}

    async def async_get_token(self, device_info: ApiDeviceInfo) -> str:
        """Return a valid SST for the device, minting/refreshing as needed."""
        did = device_info["did"]
        async with self._lock:
            cached = self._tokens.get(did)
            if cached is not None and cached.expires_at > time.time():
                return cached.token

            token = await self._issue(device_info)
            self._tokens[did] = _CachedToken(
                token, time.time() + SST_EXP_SECONDS * _SST_REFRESH_RATIO
            )
            return token

    def invalidate(self, did: str) -> None:
        """Drop any cached token for the device (e.g. after an auth failure)."""
        self._tokens.pop(did, None)

    @staticmethod
    def _sst_issue_base_url(device_info: ApiDeviceInfo) -> str:
        # SST is minted on the api-base host, derived from service.mqs
        mqs: str = device_info["service"]["mqs"]  # type: ignore[typeddict-item]
        if mqs.startswith("api-ngiot."):
            return "https://api-base." + mqs.split(".", 1)[1]
        return "https://" + mqs

    async def _issue(self, device_info: ApiDeviceInfo) -> str:
        credentials = await self._authenticator.authenticate()
        url = self._sst_issue_base_url(device_info) + SST_ISSUE_PATH
        cls = device_info["class"]
        did = device_info["did"]
        payload: dict[str, Any] = {
            "acl": [
                {
                    "policy": [
                        {"obj": [f"Endpoint:{cls}:{did}"], "perms": ["Control"]}
                    ],
                    "svc": "dim",
                }
            ],
            "exp": SST_EXP_SECONDS,
            "sub": credentials.user_id,
        }
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        _LOGGER.debug("Minting SST for device class %s", cls)
        async with self._session.post(
            url, json=payload, headers=headers, timeout=_TIMEOUT
        ) as res:
            res.raise_for_status()
            body = orjson.loads(await res.read())
        return str(body["data"]["data"]["token"])
