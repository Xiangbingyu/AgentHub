from __future__ import annotations

from typing import Any


class PromptPolicyResolver:
    def resolve(self, runtime_snapshot: dict[str, Any], *, executor_policy: dict[str, Any]) -> dict[str, Any]:
        role = runtime_snapshot["role"]
        executor_kind = executor_policy.get("kind", "internal_llm")
        default_system_profile = role
        if role == "worker" and executor_kind == "framework_cli":
            default_system_profile = "framework_worker"

        prompt_policy = {
            "system_profile": default_system_profile,
            "include_user_prompt": False,
            "user_prompt": "",
        }
        prompt_policy.update(runtime_snapshot.get("prompt_policy", {}))
        return prompt_policy
