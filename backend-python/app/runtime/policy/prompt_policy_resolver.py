from __future__ import annotations

from typing import Any


class PromptPolicyResolver:
    def resolve(self, runtime_snapshot: dict[str, Any], *, executor_config: dict[str, Any]) -> dict[str, Any]:
        role = runtime_snapshot["role"]
        prompt_policy = {
            "system_profile": role,
            "include_user_prompt": False,
            "user_prompt": "",
        }
        prompt_policy.update(runtime_snapshot.get("prompt_policy", {}))
        return prompt_policy
