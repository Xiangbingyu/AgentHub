from __future__ import annotations

from dataclasses import dataclass

from app.models.input_event import InputEventModel
from app.runtime.runtime_assembler import RuntimeBundle


@dataclass(slots=True)
class PromptBundle:
    system_prompt: str
    context_prompt: str


class PromptAssembler:
    def assemble(self, runtime: RuntimeBundle, input_event: InputEventModel) -> PromptBundle:
        system_prompt = self._build_system_prompt(runtime)
        context_prompt = self._build_context_prompt(runtime, input_event)
        return PromptBundle(
            system_prompt=system_prompt,
            context_prompt=context_prompt,
        )

    def _build_system_prompt(self, runtime: RuntimeBundle) -> str:
        return (
            f"role={runtime.prompt_profile}\n"
            f"agent_kind={runtime.agent.agent_kind}\n"
            f"run_id={runtime.agent_run.run_id}\n"
            f"workspace_id={runtime.agent_run.workspace_id}"
        )

    def _build_context_prompt(self, runtime: RuntimeBundle, input_event: InputEventModel) -> str:
        return (
            f"input_type={input_event.type.value}\n"
            f"input_payload={input_event.payload}\n"
            f"agent_status={runtime.agent_run.status}"
        )
