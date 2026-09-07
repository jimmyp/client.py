"""ngiot child lock command."""

from __future__ import annotations

from .common import NgiotSetCommand
from .state import GetState


class SetChildLock(NgiotSetCommand):
    """Set child lock command."""

    NAME = "setChildLock"
    APN = 50038
    get_command = GetState

    def __init__(self, enable: bool) -> None:
        super().__init__({"childLock": enable})
