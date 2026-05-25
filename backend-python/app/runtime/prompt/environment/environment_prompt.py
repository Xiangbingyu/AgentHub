from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


def build_environment_prompt(runtime: RuntimeBundle) -> str:
    return (
        "[ENVIRONMENT]\n"
        f"agent_id={runtime.agent.agent_id}\n"
        f"agent_name={runtime.agent.agent_name}\n"
        f"agent_kind={runtime.agent.agent_kind}\n"
        f"workspace_id={runtime.agent_run.workspace_id}\n"
        f"workspace_root={runtime.workspace_root}"
    )
