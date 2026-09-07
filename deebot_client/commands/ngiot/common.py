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

# bot offline; taken from the legacy portal errno, not yet observed on ngiot
_OFFLINE_CODE = 4200


def _response_code(response: dict[str, Any]) -> Any:
    if "code" in response:
        return response["code"]
    body = response.get("body")
    if isinstance(body, dict):
        return body.get("code")
    return None


class NgiotCommand(CommandWithMessageHandling, MessageBody, ABC):
    """Base ngiot command addressing a numeric apn surface."""

    DATA_TYPE = DataType.JSON
    APN: int

    def __init__(
        self,
        args: dict[str, Any] | list[Any] | None = None,
        *,
        apn: int | None = None,
    ) -> None:
        super().__init__(args)
        self._apn = self.APN if apn is None else apn

    def __init_subclass__(cls) -> None:
        verify_required_class_variables_exists(cls, ("APN",))
        return super().__init_subclass__()

    @property
    def apn(self) -> int:
        """Return the apn this command addresses."""
        return self._apn

    def _get_payload(self) -> dict[str, Any]:
        return self._args if isinstance(self._args, dict) else {}

    async def _execute_api_request(
        self, authenticator: Authenticator, device_info: ApiDeviceInfo
    ) -> dict[str, Any]:
        return await authenticator.post_ngiot_control(
            device_info, self._apn, self._get_payload()
        )

    def _handle_response(
        self, event_bus: EventBus, response: dict[str, Any]
    ) -> HandlingResult:
        code = _response_code(response)
        if code in (0, "0"):
            return self._handle_ok(event_bus, response)

        if code == _OFFLINE_CODE:
            _LOGGER.info('Device is offline. Could not execute command "%s"', self.NAME)
            event_bus.notify(AvailabilityEvent(available=False))
            return HandlingResult(HandlingState.FAILED)

        if code is None:
            return HandlingResult(HandlingState.ANALYSE)

        if self._is_available_check:
            _LOGGER.info(
                'Command "%s" was not successfully during availability-check. code=%s',
                self.NAME,
                code,
            )
        else:
            _LOGGER.warning(
                'Command "%s" was not successfully. code=%s', self.NAME, code
            )
        return HandlingResult(HandlingState.FAILED)

    def _handle_ok(
        self, _event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        """Handle a successful response."""
        raise NotImplementedError


class NgiotGetCommand(NgiotCommand, MessageBodyDataDict, GetCommand, ABC):
    """ngiot read command."""

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
    """ngiot write command."""

    def _handle_ok(
        self, _event_bus: EventBus, _response: dict[str, Any]
    ) -> HandlingResult:
        return HandlingResult.success()

    @classmethod
    def _handle_body(cls, _: EventBus, _body: dict[str, Any]) -> HandlingResult:
        return HandlingResult.success()


class NgiotSetCommand(NgiotExecuteCommand, ABC):
    """ngiot set command linked to a get command for optimistic updates."""

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
