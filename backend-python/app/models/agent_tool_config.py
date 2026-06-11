from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentToolConfig(BaseModel):
    name: Literal[
        "plan_tool",
        "delegate_tool",
        "code_tool",
        "bash_tool",
        "claude_code_tool",
        "opencode_tool",
        "question_tool",
    ]
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class AgentToolsetConfig(BaseModel):
    tools: list[AgentToolConfig] = Field(default_factory=list)
    auto_tool_choice: bool = False
    model_tools_enabled: bool = True
    runtime_tools_enabled: bool = True
