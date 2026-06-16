from __future__ import annotations

from pydantic import BaseModel, Field


class AgentSkillConfig(BaseModel):
    builtins_enabled: bool = True
    paths: list[str] = Field(default_factory=list)
    include_global: bool = False
    allowed_skills: list[str] = Field(default_factory=list)
