from __future__ import annotations

from typing import Any


class ExecutorConfigResolver:
    def resolve(self, runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
        executor_config = {
            "provider": "openai_compatible",
            "model": "",
        }
        executor_config.update(runtime_snapshot.get("executor_config", {}))
        return executor_config
