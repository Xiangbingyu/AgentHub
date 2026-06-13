from __future__ import annotations

from typing import TYPE_CHECKING

from agent_service.app.runtime.prompt.mode.orchestrator_mode_prompt import build_orchestrator_mode_prompt
from agent_service.app.runtime.prompt.mode.worker_mode_prompt import build_worker_mode_prompt

if TYPE_CHECKING:
    from agent_service.app.runtime.runtime_assembler import RuntimeBundle


def build_instruction_prompt(runtime: RuntimeBundle) -> str:
    instructions = ["run_input is the unified runtime entrypoint"]
    if runtime.uses_internal_executor():
        instructions.extend(
            [
                "loop decides continue, wait, or stop",
                "plan_tool is a system builtin tool for orchestrator planning when available",
                "delegate_tool is a system builtin tool for orchestrator worker delegation when available",
            ]
        )
    else:
        instructions.extend(
            [
                "AgentHub handles the outer control flow outside this execution.",
                "Focus only on the current task in the workspace and return a concise final result.",
            ]
        )

    if runtime.role == "orchestrator":
        instructions.append(build_orchestrator_mode_prompt())
    else:
        instructions.append(build_worker_mode_prompt())

    return "[INSTRUCTION]\n" + "\n".join(instructions)
