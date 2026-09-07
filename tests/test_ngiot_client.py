"""ngiot endpoint/control transport tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, Mock

from aiohttp import ClientResponseError, ClientSession
import orjson
import pytest
from testfixtures import LogCapture

from deebot_client.exceptions import ApiTimeoutError
from deebot_client.ngiot_client import (
    NGIOT_ENDPOINT_CONTROL_PATH,
    NGIOT_PROTOCOL_VERSION,
    NgiotClient,
)
from deebot_client.sst_authentication import SstAuthenticator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deebot_client.models import ApiDeviceInfo

_SST = "SST.header.payload.signature"
_OK = {"header": {}, "body": {"data": {"battery": 100}, "code": 0, "msg": "ok"}}


def _response(payload: dict[str, Any] | None = None, status: int = 200) -> MagicMock:
    payload = _OK if payload is None else payload
    response = MagicMock()
    response.read = AsyncMock(return_value=orjson.dumps(payload))
    if status >= 400:
        response.raise_for_status = Mock(
            side_effect=ClientResponseError(Mock(), (), status=status)
        )
    else:
        response.raise_for_status = Mock()
    return response


def _session(responses: Sequence[MagicMock] = (_response(),)) -> Mock:
    session = Mock(spec_set=ClientSession)
    session.post = MagicMock()
    session.post.return_value.__aenter__.side_effect = list(responses)
    return session


def _sst() -> Mock:
    sst = Mock(spec_set=SstAuthenticator)
    sst.async_get_token = AsyncMock(return_value=_SST)
    sst.invalidate = Mock()
    return sst


async def test_NgiotClient_control(ngiot_api_device_info: ApiDeviceInfo) -> None:
    session = _session()
    client = NgiotClient(session, _sst())

    result = await client.control(
        device_info=ngiot_api_device_info, apn=50011, data={"fanMode": "quiet"}
    )

    assert result == _OK
    args, kwargs = session.post.call_args
    assert (
        args[0]
        == f"https://api-ngiot.dc-na.ww.ecouser.net{NGIOT_ENDPOINT_CONTROL_PATH}"
    )
    params = kwargs["params"]
    assert params["ct"] == "q"
    assert params["eid"] == "did"
    assert params["et"] == "q287s6"
    assert params["er"] == "resource"
    assert params["apn"] == "50011"
    assert params["fmt"] == "j"
    headers = kwargs["headers"]
    assert headers["Authorization"] == f"Bearer {_SST}"
    assert headers["x-eco-request-id"] == params["si"]
    assert headers["Content-Type"] == "application/octet-stream"
    payload = orjson.loads(kwargs["data"])
    assert payload["body"] == {"data": {"fanMode": "quiet"}}
    assert payload["header"]["m"] == "request"
    assert payload["header"]["ver"] == NGIOT_PROTOCOL_VERSION


async def test_NgiotClient_retries_once_after_auth_error(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    session = _session([_response(status=401), _response()])
    sst = _sst()

    result = await NgiotClient(session, sst).control(
        device_info=ngiot_api_device_info, apn=10001, data={}
    )

    assert result == _OK
    sst.invalidate.assert_called_once_with("did")
    assert session.post.call_count == 2


async def test_NgiotClient_auth_error_twice_raises(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    session = _session([_response(status=403), _response(status=403)])

    with pytest.raises(ClientResponseError):
        await NgiotClient(session, _sst()).control(
            device_info=ngiot_api_device_info, apn=10001, data={}
        )
    assert session.post.call_count == 2


async def test_NgiotClient_other_http_error_not_retried(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    session = _session([_response(status=500)])
    sst = _sst()

    with pytest.raises(ClientResponseError):
        await NgiotClient(session, sst).control(
            device_info=ngiot_api_device_info, apn=10001, data={}
        )
    sst.invalidate.assert_not_called()
    assert session.post.call_count == 1


async def test_NgiotClient_timeout(ngiot_api_device_info: ApiDeviceInfo) -> None:
    session = _session()
    session.post.return_value.__aenter__.side_effect = TimeoutError()

    with pytest.raises(ApiTimeoutError):
        await NgiotClient(session, _sst()).control(
            device_info=ngiot_api_device_info, apn=10001, data={}
        )


async def test_NgiotClient_does_not_log_sst(
    ngiot_api_device_info: ApiDeviceInfo,
) -> None:
    with LogCapture() as log:
        await NgiotClient(_session(), _sst()).control(
            device_info=ngiot_api_device_info, apn=10001, data={}
        )

    for record in log.records:
        assert _SST not in record.getMessage()
