from __future__ import annotations

from dataclasses import dataclass

from app.models.input_event import InputEventModel
from app.runtime.runtime_assembler import RuntimeBundle


@dataclass(slots=True)
class PromptBundle:
    system_prompt: str
    context_prompt: str
    system_sections: list[str]
    context_sections: list[str]


class PromptAssembler:
    def assemble(self, runtime: RuntimeBundle, input_event: InputEventModel) -> PromptBundle:
        system_sections = self._build_system_sections(runtime)
        context_sections = self._build_context_sections(runtime, input_event)
        return PromptBundle(
            system_prompt="\n\n".join(system_sections),
            context_prompt="\n\n".join(context_sections),
            system_sections=system_sections,
            context_sections=context_sections,
        )

    def _build_system_sections(self, runtime: RuntimeBundle) -> list[str]:
        sections = [
            self._build_provider_section(runtime),
            self._build_environment_section(runtime),
            self._build_instruction_section(runtime),
            self._build_role_section(runtime),
            self._build_tool_section(runtime),
        ]

        user_prompt = runtime.prompt_plan.get("user_prompt", "").strip()
        if runtime.prompt_plan.get("include_user_prompt") and user_prompt:
            sections.append(f"[USER_CUSTOM_PROMPT]\n{user_prompt}")

        return sections

    def _build_context_sections(self, runtime: RuntimeBundle, input_event: InputEventModel) -> list[str]:
        return [
            (
                "[RUNTIME_CONTEXT]\n"
                f"run_id={runtime.agent_run.run_id}\n"
                f"workspace_id={runtime.agent_run.workspace_id}\n"
                f"workspace_root={runtime.workspace_root}\n"
                f"agent_status={runtime.agent_run.status}\n"
                f"input_type={input_event.type.value}\n"
                f"input_payload={input_event.payload}"
            )
        ]

    def _build_provider_section(self, runtime: RuntimeBundle) -> str:
        executor_kind = runtime.executor_policy.get("kind", "internal_llm")
        provider = runtime.executor_policy.get("provider") or runtime.executor_policy.get("framework") or "default"
        return (
            "[PROVIDER]\n"
            f"executor_kind={executor_kind}\n"
            f"provider={provider}\n"
            f"prompt_profile={runtime.prompt_profile}"
        )

    def _build_environment_section(self, runtime: RuntimeBundle) -> str:
        return (
            "[ENVIRONMENT]\n"
            f"agent_id={runtime.agent.agent_id}\n"
            f"agent_name={runtime.agent.agent_name}\n"
            f"agent_kind={runtime.agent.agent_kind}\n"
            f"workspace_id={runtime.agent_run.workspace_id}\n"
            f"workspace_root={runtime.workspace_root}"
        )

    def _build_instruction_section(self, runtime: RuntimeBundle) -> str:
        instructions = ["run_input is the unified runtime entrypoint"]
        if runtime.uses_internal_executor():
            instructions.extend(
                [
                    "loop decides continue, wait, or stop",
                    "plan_tool stores the complete execution plan snapshot",
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
            instructions.append("orchestrator is responsible for planning and plan maintenance")
        else:
            instructions.append("worker is responsible for task execution")
        return "[INSTRUCTION]\n" + "\n".join(instructions)

    def _build_role_section(self, runtime: RuntimeBundle) -> str:
        return (
            "[ROLE]\n"
            f"role={runtime.role}\n"
            f"system_profile={runtime.prompt_plan.get('system_profile', runtime.prompt_profile)}"
        )

    def _build_tool_section(self, runtime: RuntimeBundle) -> str:
        if not runtime.uses_internal_executor():
            allowed_tools = runtime.executor_policy.get("framework_allowed_tools", [])
            return (
                "[TOOLS]\n"
                "tool_runtime=external_framework\n"
                f"framework_allowed_tools={','.join(allowed_tools)}"
            )

        model_tools = [item["function"]["name"] for item in runtime.get_llm_tools()]
        toolset = ",".join(sorted(runtime.toolset))
        visible = ",".join(model_tools) if model_tools else "(none)"
        return (
            "[TOOLS]\n"
            "tool_runtime=internal\n"
            f"runtime_toolset={toolset}\n"
            f"model_visible_tools={visible}"
        )
