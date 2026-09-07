"""ngiot life span command tests."""

from __future__ import annotations

import re

import pytest

from deebot_client.commands.ngiot.life_span import ResetLifeSpan
from deebot_client.events import LifeSpan

from . import assert_command, ngiot_response


@pytest.mark.parametrize(
    ("life_span", "consumable"),
    [
        (LifeSpan.BRUSH, "rollBrush"),
        (LifeSpan.FILTER, "filter"),
        (LifeSpan.SIDE_BRUSH, "sideBrush"),
        (LifeSpan.UNIT_CARE, "unitCare"),
    ],
)
async def test_ResetLifeSpan(life_span: LifeSpan, consumable: str) -> None:
    await assert_command(
        ResetLifeSpan(life_span),
        ngiot_response(),
        None,
        expected_apn=50017,
        expected_data={"resetConsumable": consumable},
    )


def test_ResetLifeSpan_unsupported() -> None:
    with pytest.raises(ValueError, match=re.escape("LifeSpan.BLADE")):
        ResetLifeSpan(LifeSpan.BLADE)
