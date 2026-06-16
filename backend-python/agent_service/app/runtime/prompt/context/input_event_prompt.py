from __future__ import annotations

from typing import TYPE_CHECKING

from agent_service.app.models.input_event import InputEventModel

if TYPE_CHECKING:
    from agent_service.app.runtime.runtime_assembler import RuntimeBundle


def build_input_event_prompt(runtime: RuntimeBundle, input_event: InputEventModel) -> str:
    return (
        "[RUNTIME_CONTEXT]\n"
        f"run_id={runtime.agent_run.run_id}\n"
        f"workspace_id={runtime.agent_run.workspace_id}\n"
        f"workspace_root={runtime.workspace_root}\n"
        f"agent_status={runtime.agent_run.status}\n"
        f"input_type={input_event.type.value}\n"
        f"input_payload={input_event.payload}"
    )
