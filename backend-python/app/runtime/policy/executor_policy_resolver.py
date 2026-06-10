from __future__ import annotations

from typing import Any


class ExecutorPolicyResolver:
    def resolve(self, runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
        executor_policy = {
            "kind": "internal_llm",
            "provider": "openai_compatible",
            "model": "",
            "framework": None,
            "command": None,
            "timeout_seconds": 300,
            "framework_options": {},
        }
        executor_policy.update(runtime_snapshot.get("executor_policy", {}))
        framework_options = dict(executor_policy.get("framework_options") or {})
        if "allowed_tools" not in framework_options and executor_policy.get("framework_allowed_tools"):
            framework_options["allowed_tools"] = list(executor_policy["framework_allowed_tools"])
        if "permission_mode" not in framework_options and executor_policy.get("permission_mode") is not None:
            framework_options["permission_mode"] = executor_policy["permission_mode"]
        if "allow_dangerously_skip_permissions" not in framework_options:
            framework_options["allow_dangerously_skip_permissions"] = bool(
                executor_policy.get("allow_dangerously_skip_permissions", False)
            )
        if "dangerously_skip_permissions" not in framework_options:
            framework_options["dangerously_skip_permissions"] = bool(
                executor_policy.get("dangerously_skip_permissions", False)
            )
        if executor_policy.get("kind") == "framework_cli" and not executor_policy.get("command"):
            executor_policy["command"] = executor_policy.get("framework") or "claude"
        executor_policy["framework_options"] = framework_options
        executor_policy.pop("framework_allowed_tools", None)
        executor_policy.pop("permission_mode", None)
        executor_policy.pop("allow_dangerously_skip_permissions", None)
        executor_policy.pop("dangerously_skip_permissions", None)
        return executor_policy
