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
        executor_kind = executor_policy.get("kind", "internal_llm")
        default_toolset = "orchestrator_default" if role == "orchestrator" else "worker_default"
        tool_policy = {
            "system_toolset": default_toolset,
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
        tool_policy.update(runtime_snapshot.get("tool_policy", {}))
        if executor_kind != "internal_llm":
            tool_policy["system_toolset"] = "none"
            tool_policy["model_tools_enabled"] = False
            tool_policy["runtime_tools_enabled"] = False
            tool_policy["auto_tool_choice"] = False
        return tool_policy
