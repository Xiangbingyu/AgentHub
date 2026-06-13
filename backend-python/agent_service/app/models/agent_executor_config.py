from __future__ import annotations

from pydantic import BaseModel


class AgentExecutorConfig(BaseModel):
    provider: str = "openai_compatible"
    model: str = ""
