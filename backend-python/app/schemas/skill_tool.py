from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SkillToolRequest(BaseModel):
    name: str


def build_skill_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "skill_tool",
            "description": "Load a skill by name from the available_skills list.",
            "parameters": SkillToolRequest.model_json_schema(),
        },
    }
