"""q287s6 fire-and-forget action commands (play-sound and life-span reset).

Action surfaces captured live from the official app and confirmed against a
real device (see ``tools/NGIOT_Q287S6_PROTOCOL.md``):
play-sound / locate (40019 ``seek:true``) and reset-consumable (50017
``resetConsumable:<type>``). Both are momentary actions: success is the
envelope ``code`` and there is no telemetry to parse back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .common import NgiotExecuteCommand
from .state import NGIOT_LIFESPAN_TO_CONSUMABLE

if TYPE_CHECKING:
    from deebot_client.events import LifeSpan


class PlaySound(NgiotExecuteCommand):
    """Play a sound to locate the bot (apn 40019, ``seek:true``)."""

    NAME = "playSound"
    APN = 40019

    def __init__(self) -> None:
        super().__init__({"seek": True})


class ResetLifeSpan(NgiotExecuteCommand):
    """Reset a consumable life-span counter (apn 50017).

    The device's consumable names do NOT match the :class:`LifeSpan` enum values
    (``LifeSpan.BRUSH.value`` is ``"brush"``, ``LifeSpan.FILTER.value`` is
    ``"heap"``), so the type string is taken from the explicit
    :data:`~deebot_client.commands.ngiot.state.NGIOT_LIFESPAN_TO_CONSUMABLE` map
    rather than ``life_span.value``.
    """

    NAME = "resetLifeSpan"
    APN = 50017

    def __init__(self, life_span: LifeSpan) -> None:
        super().__init__({"resetConsumable": NGIOT_LIFESPAN_TO_CONSUMABLE[life_span]})
