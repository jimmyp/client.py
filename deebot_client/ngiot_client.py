"""ngiot endpoint/control transport."""

from __future__ import annotations

from http import HTTPStatus
import secrets
import time
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError, ClientTimeout
import orjson

from .exceptions import ApiTimeoutError
from .logging_filter import get_logger

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from .models import ApiDeviceInfo
    from .sst_authentication import SstAuthenticator

_LOGGER = get_logger(__name__)

NGIOT_ENDPOINT_CONTROL_PATH = "/api/iot/endpoint/control"
NGIOT_PROTOCOL_VERSION = "0.0.22"
_USER_AGENT = "okhttp/4.9.1"
_TIMEOUT = ClientTimeout(60)
_AUTH_ERROR_STATUSES = {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}


class NgiotClient:
    """Perform ngiot endpoint/control calls for a device."""

    def __init__(
        self, session: ClientSession, sst_authenticator: SstAuthenticator
    ) -> None:
        self._session = session
        self._sst = sst_authenticator

    async def control(
        self, *, device_info: ApiDeviceInfo, apn: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a control call to the numeric surface (apn) and return the response."""
        # control is served by the service.mqs host
        url = f"https://{device_info['service']['mqs']}{NGIOT_ENDPOINT_CONTROL_PATH}"
        _LOGGER.debug("ngiot control apn=%s class=%s", apn, device_info["class"])
        try:
            return await self._post(url, device_info, apn, data)
        except ClientResponseError as ex:
            if ex.status not in _AUTH_ERROR_STATUSES:
                raise
            # the SST was rejected; drop it and retry once with a fresh one
            self._sst.invalidate(device_info["did"])
            return await self._post(url, device_info, apn, data)

    async def _post(
        self, url: str, device_info: ApiDeviceInfo, apn: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        sst = await self._sst.async_get_token(device_info)
        si = secrets.token_hex(16)
        params = {
            "si": si,
            "ct": "q",
            "eid": device_info["did"],
            "et": device_info["class"],
            "er": device_info["resource"],
            "apn": str(apn),
            "fmt": "j",
        }
        payload = {
            "body": {"data": data},
            "header": {
                "channel": "Android",
                "m": "request",
                "pri": 2,
                "reqid": secrets.token_hex(3),
                "ts": str(int(time.time() * 1000)),
                "tzc": "UTC",
                "tzm": 0,
                "ver": NGIOT_PROTOCOL_VERSION,
            },
        }
        headers = {
            "Authorization": f"Bearer {sst}",
            "x-eco-request-id": si,
            "Content-Type": "application/octet-stream",
            "User-Agent": _USER_AGENT,
        }
        try:
            async with self._session.post(
                url,
                params=params,
                data=orjson.dumps(payload),
                headers=headers,
                timeout=_TIMEOUT,
            ) as res:
                res.raise_for_status()
                raw = await res.read()
        except TimeoutError as ex:
            raise ApiTimeoutError(
                path=NGIOT_ENDPOINT_CONTROL_PATH, timeout=_TIMEOUT
            ) from ex
        response: dict[str, Any] = orjson.loads(raw)
        return response
