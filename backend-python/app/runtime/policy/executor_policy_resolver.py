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
        executor_policy.update(runtime_snapshot.get("executor_config", {}))
        framework_options = dict(executor_policy.get("framework_options") or {})
        executor_policy["framework_options"] = framework_options
        return executor_policy
