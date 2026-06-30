"""q287s6 state command (apn 10001)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.const import ERROR_CODES
from deebot_client.events import (
    BatteryEvent,
    ChildLockEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    LifeSpan,
    LifeSpanEvent,
    StateEvent,
    VolumeEvent,
)
from deebot_client.events.station import State as StationState, StationEvent
from deebot_client.events.water_info import (
    MopAttachedEvent,
    WaterAmount,
    WaterAmountEvent,
)
from deebot_client.logging_filter import get_logger
from deebot_client.message import HandlingResult
from deebot_client.models import State

from .common import NgiotGetCommand

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus

_LOGGER = get_logger(__name__)

# fields requested in the state read
STATE_FIELDS = [
    "battery",
    "chargeStatus",
    "stationStatus",
    "stationType",
    "fanMode",
    "waterMode",
    "workMode",
    "mopState",
    "pauseSwitch",
    "status",
    "error",
    "consumables",
    "volume",
    "childLock",
]

# ngiot fanMode <-> FanSpeedLevel ("auto" has no dedicated level -> NORMAL)
NGIOT_FAN_MODE_TO_LEVEL = {
    "auto": FanSpeedLevel.NORMAL,
    "quiet": FanSpeedLevel.QUIET,
    "standard": FanSpeedLevel.NORMAL,
    "normal": FanSpeedLevel.NORMAL,
    "strong": FanSpeedLevel.MAX,
    "max": FanSpeedLevel.MAX_PLUS,
}
NGIOT_LEVEL_TO_FAN_MODE = {
    FanSpeedLevel.QUIET: "quiet",
    FanSpeedLevel.NORMAL: "auto",
    FanSpeedLevel.MAX: "strong",
    FanSpeedLevel.MAX_PLUS: "max",
}

# ngiot waterMode <-> WaterAmount (wire value is "mid", not "medium")
NGIOT_WATER_MODE_TO_AMOUNT = {
    "low": WaterAmount.LOW,
    "mid": WaterAmount.MEDIUM,
    "high": WaterAmount.HIGH,
    "ultraHigh": WaterAmount.ULTRAHIGH,
}
NGIOT_AMOUNT_TO_WATER_MODE = {
    WaterAmount.LOW: "low",
    WaterAmount.MEDIUM: "mid",
    WaterAmount.HIGH: "high",
    WaterAmount.ULTRAHIGH: "ultraHigh",
}

# ngiot consumable type -> LifeSpan component.
NGIOT_CONSUMABLE_TO_LIFESPAN = {
    "sideBrush": LifeSpan.SIDE_BRUSH,
    "rollBrush": LifeSpan.BRUSH,
    "filter": LifeSpan.FILTER,
    "unitCare": LifeSpan.UNIT_CARE,
}
# LifeSpan -> ngiot consumable type for the reset write (values differ from the enum)
NGIOT_LIFESPAN_TO_CONSUMABLE = {
    LifeSpan.BRUSH: "rollBrush",
    LifeSpan.FILTER: "filter",
    LifeSpan.SIDE_BRUSH: "sideBrush",
    LifeSpan.UNIT_CARE: "unitCare",
}

_STATUS_TO_STATE = {
    "smartClean": State.CLEANING,
    "clean": State.CLEANING,
    "working": State.CLEANING,
    "goCharging": State.RETURNING,
    "idle": State.IDLE,
}


def _error_code(data: dict[str, Any]) -> int | None:
    if "error" not in data:
        return None
    codes = data["error"]
    if not isinstance(codes, list):
        return None
    return codes[-1] if codes else 0


def _determine_state(data: dict[str, Any], error_code: int | None) -> State | None:
    if error_code:
        return State.ERROR
    if data.get("pauseSwitch"):
        return State.PAUSED
    if data.get("chargeStatus"):
        return State.DOCKED
    status = data.get("status")
    return _STATUS_TO_STATE.get(status) if isinstance(status, str) else None


def handle_state_fields(event_bus: EventBus, data: dict[str, Any]) -> HandlingResult:
    """Fan a ngiot ``body.data`` field dict out to events.

    Shared by the polled :class:`GetState` (apn 10001 read) and the pushed MQTT
    state messages, which carry the same flat field dict. Notifies only the
    events whose fields are present, so a partial push updates just those.
    """
    if "battery" in data:
        event_bus.notify(BatteryEvent(int(data["battery"])))

    error_code = _error_code(data)
    if (state := _determine_state(data, error_code)) is not None:
        event_bus.notify(StateEvent(state))

    if (fan_mode := data.get("fanMode")) is not None:
        if fan_mode in NGIOT_FAN_MODE_TO_LEVEL:
            event_bus.notify(FanSpeedEvent(NGIOT_FAN_MODE_TO_LEVEL[fan_mode]))
        else:
            _LOGGER.warning("Unmapped ngiot fanMode %r; please report it", fan_mode)

    if (water_mode := data.get("waterMode")) is not None:
        if water_mode in NGIOT_WATER_MODE_TO_AMOUNT:
            event_bus.notify(WaterAmountEvent(NGIOT_WATER_MODE_TO_AMOUNT[water_mode]))
        else:
            _LOGGER.warning("Unmapped ngiot waterMode %r; please report it", water_mode)

    if (mop_state := data.get("mopState")) is not None:
        event_bus.notify(MopAttachedEvent(mop_state == "installed"))

    if error_code is not None:
        event_bus.notify(ErrorEvent(error_code, ERROR_CODES.get(error_code)))

    if isinstance(data.get("consumables"), list):
        _notify_consumables(event_bus, data["consumables"])

    station_status = data.get("stationStatus")
    if isinstance(station_status, int) and not isinstance(station_status, bool):
        event_bus.notify(StationEvent(StationState(station_status)))

    _notify_settings(event_bus, data)

    return HandlingResult.success()


def _notify_settings(event_bus: EventBus, data: dict[str, Any]) -> None:
    if (volume := data.get("volume")) is not None:
        event_bus.notify(VolumeEvent(int(volume), maximum=None))

    if (child_lock := data.get("childLock")) is not None:
        event_bus.notify(ChildLockEvent(bool(child_lock)))


def _notify_consumables(event_bus: EventBus, consumables: list[dict[str, Any]]) -> None:
    for component in consumables:
        comp_type = component.get("type")
        life_span = (
            NGIOT_CONSUMABLE_TO_LIFESPAN.get(comp_type)
            if isinstance(comp_type, str)
            else None
        )
        if life_span is None:
            continue
        total = int(component["total"])
        if total <= 0:
            continue
        left = int(component["left"])
        percent = round((left / total) * 100, 2)
        event_bus.notify(LifeSpanEvent(life_span, percent, left))


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
        return handle_state_fields(event_bus, data)
