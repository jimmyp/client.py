"""q287s6 state command (apn 10001 comprehensive field read).

A single ``endpoint/control`` read of surface ``10001`` returns the bulk of the
device telemetry as a flat ``body.data`` dict. This command fans those fields
out to the individual events the rest of the library consumes.

Verified against the live capture in ``tools/NGIOT_Q287S6_PROTOCOL.md``:
battery, fanMode, waterMode, mopState, error and consumables all parse from the
real response. The vacuum *state* mapping (idle/clean/return/dock/error/pause)
is best-effort -- only the unambiguous transitions are emitted; see
``_determine_state``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deebot_client.const import ERROR_CODES
from deebot_client.events import (
    BatteryEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    LifeSpan,
    LifeSpanEvent,
    StateEvent,
)
from deebot_client.events.station import State as StationState, StationEvent
from deebot_client.events.water_info import (
    MopAttachedEvent,
    WaterAmount,
    WaterAmountEvent,
)
from deebot_client.message import HandlingResult
from deebot_client.models import State

from .common import NgiotGetCommand

if TYPE_CHECKING:
    from deebot_client.event_bus import EventBus

# Fields requested in the comprehensive state read.
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
]

# ngiot fanMode <-> FanSpeedLevel. Wire-verified: "quiet", "strong".
# "normal"/"max" enum names are inferred and refined by live capture.
NGIOT_FAN_MODE_TO_LEVEL = {
    "quiet": FanSpeedLevel.QUIET,
    "standard": FanSpeedLevel.NORMAL,
    "normal": FanSpeedLevel.NORMAL,
    "strong": FanSpeedLevel.MAX,
    "max": FanSpeedLevel.MAX_PLUS,
}
NGIOT_LEVEL_TO_FAN_MODE = {
    FanSpeedLevel.QUIET: "quiet",
    FanSpeedLevel.NORMAL: "normal",
    FanSpeedLevel.MAX: "strong",
    FanSpeedLevel.MAX_PLUS: "max",
}

# ngiot waterMode <-> WaterAmount. Wire-verified: "low", "high".
NGIOT_WATER_MODE_TO_AMOUNT = {
    "low": WaterAmount.LOW,
    "medium": WaterAmount.MEDIUM,
    "high": WaterAmount.HIGH,
    "ultraHigh": WaterAmount.ULTRAHIGH,
}
NGIOT_AMOUNT_TO_WATER_MODE = {
    WaterAmount.LOW: "low",
    WaterAmount.MEDIUM: "medium",
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


class GetState(NgiotGetCommand):
    """Read the comprehensive q287s6 device state (apn 10001)."""

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

        if (fan_mode := data.get("fanMode")) in NGIOT_FAN_MODE_TO_LEVEL:
            event_bus.notify(FanSpeedEvent(NGIOT_FAN_MODE_TO_LEVEL[fan_mode]))

        if (water_mode := data.get("waterMode")) in NGIOT_WATER_MODE_TO_AMOUNT:
            event_bus.notify(WaterAmountEvent(NGIOT_WATER_MODE_TO_AMOUNT[water_mode]))

        if (mop_state := data.get("mopState")) is not None:
            event_bus.notify(MopAttachedEvent(mop_state == "installed"))

        if error_code is not None:
            event_bus.notify(ErrorEvent(error_code, ERROR_CODES.get(error_code)))

        if isinstance(data.get("consumables"), list):
            cls._notify_consumables(event_bus, data["consumables"])

        station_status = data.get("stationStatus")
        if isinstance(station_status, int) and not isinstance(station_status, bool):
            event_bus.notify(StationEvent(StationState(station_status)))

        return HandlingResult.success()

    @staticmethod
    def _notify_consumables(
        event_bus: EventBus, consumables: list[dict[str, Any]]
    ) -> None:
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
