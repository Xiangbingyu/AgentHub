from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentMcpServerConfig(BaseModel):
    name: str
    enabled: bool = True
    type: Literal["local", "remote"]
    preset: str | None = None
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class AgentMcpConfig(BaseModel):
    enabled: bool = False
    servers: list[AgentMcpServerConfig] = Field(default_factory=list)
