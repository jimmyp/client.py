"""ngiot play-sound and life-span reset command tests."""

from __future__ import annotations

from typing import Any

import pytest

from deebot_client.commands.ngiot.actions import PlaySound, ResetLifeSpan
from deebot_client.events import LifeSpan

from . import assert_ngiot_command

_OK: dict[str, Any] = {"header": {}, "body": {"data": None, "code": 0, "msg": "ok"}}


async def test_PlaySound_locates_the_bot() -> None:
    # apn 40019 {seek: true}; momentary action, no events
    await assert_ngiot_command(
        PlaySound(),
        _OK,
        None,
        expected_apn=40019,
        expected_data={"seek": True},
    )


@pytest.mark.parametrize(
    ("life_span", "expected_consumable"),
    [
        # wire type comes from the explicit map, not life_span.value
        (LifeSpan.BRUSH, "rollBrush"),
        (LifeSpan.FILTER, "filter"),
        (LifeSpan.SIDE_BRUSH, "sideBrush"),
        (LifeSpan.UNIT_CARE, "unitCare"),
    ],
)
async def test_ResetLifeSpan(life_span: LifeSpan, expected_consumable: str) -> None:
    await assert_ngiot_command(
        ResetLifeSpan(life_span),
        _OK,
        None,
        expected_apn=50017,
        expected_data={"resetConsumable": expected_consumable},
    )
