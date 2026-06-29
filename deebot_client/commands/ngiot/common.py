"""Base ngiot commands."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from deebot_client.command import CommandWithMessageHandling, GetCommand
from deebot_client.const import DataType
from deebot_client.events import AvailabilityEvent
from deebot_client.logging_filter import get_logger
from deebot_client.message import (
    HandlingResult,
    HandlingState,
    MessageBody,
    MessageBodyDataDict,
)
from deebot_client.util import verify_required_class_variables_exists

if TYPE_CHECKING:
    from deebot_client.authentication import Authenticator
    from deebot_client.event_bus import EventBus
    from deebot_client.models import ApiDeviceInfo

_LOGGER = get_logger(__name__)

# bot offline
_OFFLINE_CODE = 4200


def _envelope_code(response: dict[str, Any]) -> Any:
    """Extract the endpoint/control result code (top-level or body level)."""
    if "code" in response:
        return response["code"]
    body = response.get("body")
    if isinstance(body, dict) and "code" in body:
        return body["code"]
    return None


class NgiotCommand(CommandWithMessageHandling, MessageBody, ABC):
    """Base ngiot command addressing a numeric apn surface."""

    DATA_TYPE = DataType.JSON
    APN: int

    def __init_subclass__(cls) -> None:
        verify_required_class_variables_exists(cls, ("APN",))
        return super().__init_subclass__()

    def _get_payload(self) -> dict[str, Any]:
        return self._args if isinstance(self._args, dict) else {}

    async def _execute_api_request(
        self, authenticator: Authenticator, device_info: ApiDeviceInfo
    ) -> dict[str, Any]:
        return await authenticator.ngiot.control(
            device_info=device_info, apn=self.APN, data=self._get_payload()
        )

    def _handle_response(
        self, event_bus: EventBus, response: dict[str, Any]
    ) -> HandlingResult:
        code = _envelope_code(response)
        if code in (0, "0", None):
            return self._handle_ok(event_bus, response)

        if code == _OFFLINE_CODE:
            _LOGGER.info('Device is offline. Could not execute command "%s"', self.NAME)
            event_bus.notify(AvailabilityEvent(available=False))
            return HandlingResult(HandlingState.FAILED)

        _LOGGER.warning('Command "%s" was not successfully. code=%s', self.NAME, code)
        return HandlingResult(HandlingState.FAILED)

    def _handle_ok(
        self, _event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        """Handle a successful (code 0) response."""
        raise NotImplementedError


class NgiotGetCommand(NgiotCommand, MessageBodyDataDict, GetCommand, ABC):
    """ngiot read command: query a list of fields and parse ``body.data``."""

    def __init__(self, fields: list[str] | None = None) -> None:
        super().__init__({"fields": fields} if fields is not None else {})

    def _handle_ok(
        self, event_bus: EventBus, response: dict[str, Any]
    ) -> HandlingResult:
        result = self.handle(event_bus, response)
        return HandlingResult(result.state, result.args)

    @classmethod
    def handle_set_args(
        cls, event_bus: EventBus, args: dict[str, Any]
    ) -> HandlingResult:
        """Handle arguments of set command."""
        return cls._handle_body_data_dict(event_bus, args)


class NgiotExecuteCommand(NgiotCommand, ABC):
    """ngiot write/action command: success is determined by the envelope code."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        super().__init__(data or {})

    def _handle_ok(
        self, _event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        return HandlingResult.success()

    @classmethod
    def _handle_body(cls, _: EventBus, _body: dict[str, Any]) -> HandlingResult:
        return HandlingResult.success()


class NgiotSetCommand(NgiotExecuteCommand, ABC):
    """ngiot set command linked to a get command for optimistic event updates."""

    @property
    def get_command(self) -> type[NgiotGetCommand]:
        """Return the corresponding ngiot get command."""
        raise NotImplementedError

    def _handle_ok(
        self, event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        if isinstance(self._args, dict):
            self.get_command.handle_set_args(event_bus, self._args)
        return HandlingResult.success()


__all__ = [
    "NgiotCommand",
    "NgiotExecuteCommand",
    "NgiotGetCommand",
    "NgiotSetCommand",
]
