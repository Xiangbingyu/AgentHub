from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 16384


class AgentTemplateRecord(BaseModel):
    agent_id: str
    name: str
    role: str
    system_prompt: str
    default_model_config: ModelConfig
    default_tool_policy: dict = Field(default_factory=dict)
    default_mcp_refs: list[str] = Field(default_factory=list)
    default_skill_refs: list[str] = Field(default_factory=list)
    default_permission_policy: dict = Field(default_factory=dict)


class TeamRecord(BaseModel):
    team_id: str
    name: str
    description: str = ""
    leader_agent_id: str
    member_agent_ids: list[str] = Field(default_factory=list)
    enabled_tool_policy: dict = Field(default_factory=dict)
    enabled_mcp_refs: list[str] = Field(default_factory=list)
    enabled_skill_refs: list[str] = Field(default_factory=list)
    is_default: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
