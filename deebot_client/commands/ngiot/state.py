"""ngiot state command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.const import ERROR_CODES
from deebot_client.events import (
    BatteryEvent,
    ChildLockEvent,
    ErrorEvent,
    FanSpeedEvent,
    LifeSpanEvent,
    StateEvent,
    VolumeEvent,
)
from deebot_client.events.network import NetworkInfoEvent
from deebot_client.events.water_info import MopAttachedEvent, WaterAmountEvent
from deebot_client.logging_filter import get_logger
from deebot_client.message import HandlingResult
from deebot_client.models import State

from .common import NgiotGetCommand
from .const import CONSUMABLE_TO_LIFE_SPAN, FAN_MODE_TO_LEVEL, WATER_MODE_TO_AMOUNT

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus

_LOGGER = get_logger(__name__)

STATE_FIELDS = [
    "battery",
    "chargeStatus",
    "fanMode",
    "waterMode",
    "mopState",
    "pauseSwitch",
    "status",
    "error",
    "consumables",
    "volume",
    "childLock",
    "deviceInfo",
]

_STATUS_TO_STATE = {
    "smartClean": State.CLEANING,
    "goCharge": State.RETURNING,
}


def _error_code(data: dict[str, Any]) -> int | None:
    codes = data.get("error")
    if not isinstance(codes, list):
        return None
    return int(codes[-1]) if codes else 0


def _determine_state(data: dict[str, Any], error_code: int | None) -> State | None:
    if error_code:
        return State.ERROR
    if data.get("chargeStatus"):
        return State.DOCKED
    if data.get("pauseSwitch"):
        return State.PAUSED
    status = data.get("status")
    if not isinstance(status, str):
        return None
    state = _STATUS_TO_STATE.get(status)
    if state is None:
        _LOGGER.debug("Unmapped ngiot status %r", status)
    return state


def _notify_fan_mode(event_bus: EventBus, data: dict[str, Any]) -> None:
    if (fan_mode := data.get("fanMode")) is None:
        return
    if (level := FAN_MODE_TO_LEVEL.get(fan_mode)) is not None:
        event_bus.notify(FanSpeedEvent(level))
    else:
        _LOGGER.debug("Unmapped ngiot fanMode %r", fan_mode)


def _notify_water_mode(event_bus: EventBus, data: dict[str, Any]) -> None:
    if (water_mode := data.get("waterMode")) is None:
        return
    if (amount := WATER_MODE_TO_AMOUNT.get(water_mode)) is not None:
        event_bus.notify(WaterAmountEvent(amount))
    else:
        _LOGGER.debug("Unmapped ngiot waterMode %r", water_mode)


class GetState(NgiotGetCommand):
    """Get state command."""

    NAME = "getState"
    APN = 10001

    def __init__(self, *, is_available_check: bool = False) -> None:
        super().__init__(STATE_FIELDS)
        self._is_available_check = is_available_check

    @classmethod
    def _handle_body_data_dict(
        cls, event_bus: EventBus, data: dict[str, Any]
    ) -> HandlingResult:
        if "battery" in data:
            event_bus.notify(BatteryEvent(int(data["battery"])))

        error_code = _error_code(data)
        if (state := _determine_state(data, error_code)) is not None:
            event_bus.notify(StateEvent(state))

        _notify_fan_mode(event_bus, data)
        _notify_water_mode(event_bus, data)

        if (mop_state := data.get("mopState")) is not None:
            event_bus.notify(MopAttachedEvent(mop_state == "installed"))

        if error_code is not None:
            event_bus.notify(ErrorEvent(error_code, ERROR_CODES.get(error_code)))

        if isinstance(consumables := data.get("consumables"), list):
            cls._notify_consumables(event_bus, consumables)

        if (volume := data.get("volume")) is not None:
            event_bus.notify(VolumeEvent(int(volume), maximum=None))

        if (child_lock := data.get("childLock")) is not None:
            event_bus.notify(ChildLockEvent(bool(child_lock)))

        if isinstance(device_info := data.get("deviceInfo"), dict):
            cls._notify_network(event_bus, device_info)

        return HandlingResult.success()

    @staticmethod
    def _notify_consumables(
        event_bus: EventBus, consumables: list[dict[str, Any]]
    ) -> None:
        for component in consumables:
            comp_type = component.get("type")
            if not isinstance(comp_type, str):
                continue
            life_span = CONSUMABLE_TO_LIFE_SPAN.get(comp_type)
            if life_span is None:
                continue
            try:
                total = int(component["total"])
                left = int(component["left"])
            except KeyError, TypeError, ValueError:
                _LOGGER.debug("Malformed ngiot consumable %s", comp_type)
                continue
            if total <= 0:
                continue
            percent = round((left / total) * 100, 2)
            event_bus.notify(LifeSpanEvent(life_span, percent, left))

    @staticmethod
    def _notify_network(event_bus: EventBus, device_info: dict[str, Any]) -> None:
        try:
            event = NetworkInfoEvent(
                ip=str(device_info["ip"]),
                ssid=str(device_info["ssid"]),
                rssi=int(float(device_info["rssi"])),
                mac=str(device_info["mac"]),
            )
        except KeyError, TypeError, ValueError:
            _LOGGER.debug("Incomplete ngiot deviceInfo")
            return
        event_bus.notify(event)
