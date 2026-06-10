from __future__ import annotations

from typing import Any


class ToolPolicyResolver:
    def resolve(
        self,
        runtime_snapshot: dict[str, Any],
        *,
        role: str,
        executor_policy: dict[str, Any],
    ) -> dict[str, Any]:
        tool_policy = {
            "tools": [],
            "user_tools": [],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
            "command_policies": {
                "bash": {
                    "*": "allow",
                }
            },
        }
        tool_policy.update(runtime_snapshot.get("tool_config", {}))
        return tool_policy
