from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LlmMessage:
    role: str
    content: str


@dataclass(slots=True)
class LlmRequest:
    system_prompt: str
    tool_prompt: str
    context_prompt: str
    messages: list[LlmMessage] = field(default_factory=list)
    model: str = ""


@dataclass(slots=True)
class LlmResponse:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
