from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LoopAction(str, Enum):
    continue_ = "continue"
    wait = "wait"
    stop = "stop"


@dataclass(slots=True)
class LoopResult:
    action: LoopAction
    next_status: str | None = None
    reason: str | None = None
