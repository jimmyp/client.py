"""ngiot command constants."""

from __future__ import annotations

from deebot_client.events import FanSpeedLevel, LifeSpan
from deebot_client.events.water_info import WaterAmount

# "auto" is the device default and has no dedicated level
FAN_MODE_TO_LEVEL = {
    "auto": FanSpeedLevel.NORMAL,
    "quiet": FanSpeedLevel.QUIET,
    "strong": FanSpeedLevel.MAX,
    "max": FanSpeedLevel.MAX_PLUS,
}
LEVEL_TO_FAN_MODE = {level: mode for mode, level in FAN_MODE_TO_LEVEL.items()}

WATER_MODE_TO_AMOUNT = {
    "low": WaterAmount.LOW,
    "mid": WaterAmount.MEDIUM,
    "high": WaterAmount.HIGH,
}
AMOUNT_TO_WATER_MODE = {amount: mode for mode, amount in WATER_MODE_TO_AMOUNT.items()}

CONSUMABLE_TO_LIFE_SPAN = {
    "sideBrush": LifeSpan.SIDE_BRUSH,
    "rollBrush": LifeSpan.BRUSH,
    "filter": LifeSpan.FILTER,
    "unitCare": LifeSpan.UNIT_CARE,
}
LIFE_SPAN_TO_CONSUMABLE = {
    life_span: consumable for consumable, life_span in CONSUMABLE_TO_LIFE_SPAN.items()
}
