from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AgentExecutorConfig(BaseModel):
    kind: Literal["internal_llm"] = "internal_llm"
    provider: str = "openai_compatible"
    model: str = ""
