from __future__ import annotations

from dataclasses import dataclass, field

from app.models.input_event import InputEventModel
from app.runtime.prompt.context.input_event_prompt import build_input_event_prompt
from app.runtime.prompt.environment.environment_prompt import build_environment_prompt
from app.runtime.prompt.instruction.instruction_prompt import build_instruction_prompt
from app.runtime.runtime_assembler import RuntimeBundle


@dataclass(slots=True)
class PromptSection:
    name: str
    source: str
    content: str


@dataclass(slots=True)
class PromptView:
    system_prompt: str
    context_prompt: str
    system_sections: list[PromptSection] = field(default_factory=list)
    context_sections: list[PromptSection] = field(default_factory=list)


class PromptComposer:
    def compose(self, runtime: RuntimeBundle, input_event: InputEventModel) -> PromptView:
        system_sections = self._build_system_sections(runtime)
        context_sections = self._build_context_sections(runtime, input_event)
        return PromptView(
            system_prompt="\n\n".join(section.content for section in system_sections),
            context_prompt="\n\n".join(section.content for section in context_sections),
            system_sections=system_sections,
            context_sections=context_sections,
        )

    def _build_system_sections(self, runtime: RuntimeBundle) -> list[PromptSection]:
        sections = [
            self._section("provider", "runtime", self._build_provider_section(runtime)),
            self._section("environment", "runtime", build_environment_prompt(runtime)),
            self._section("instruction", "runtime", build_instruction_prompt(runtime)),
            self._build_project_instruction_section(runtime),
            self._section("role", "runtime", self._build_role_section(runtime)),
            self._section("tools", "runtime", self._build_tool_section(runtime)),
        ]

        user_prompt = str(runtime.prompt_policy.get("user_prompt", "")).strip()
        if runtime.prompt_policy.get("include_user_prompt") and user_prompt:
            sections.append(self._section("user_custom_prompt", "prompt_policy", f"[USER_CUSTOM_PROMPT]\n{user_prompt}"))

        return [section for section in sections if section is not None]

    def _build_context_sections(self, runtime: RuntimeBundle, input_event: InputEventModel) -> list[PromptSection]:
        return [
            self._section(
                "runtime_context",
                "runtime",
                build_input_event_prompt(runtime, input_event),
            )
        ]

    def _build_provider_section(self, runtime: RuntimeBundle) -> str:
        executor_kind = runtime.executor_config.get("kind", "internal_llm")
        provider = runtime.executor_config.get("provider") or "default"
        prompt_profile = str(runtime.prompt_policy.get("system_profile", ""))
        return (
            "[PROVIDER]\n"
            f"executor_kind={executor_kind}\n"
            f"provider={provider}\n"
            f"prompt_profile={prompt_profile}"
        )

    def _build_project_instruction_section(self, runtime: RuntimeBundle) -> PromptSection | None:
        if runtime.instruction_view is None or not runtime.instruction_view.items:
            return None

        rendered_items = []
        for item in runtime.instruction_view.items:
            rendered_items.append(f"[SOURCE]\n{item.source}\n[CONTENT]\n{item.content}")
        return self._section(
            "project_instructions",
            "instruction_view",
            "[PROJECT_INSTRUCTIONS]\n" + "\n\n".join(rendered_items),
        )

    def _build_role_section(self, runtime: RuntimeBundle) -> str:
        system_profile = str(runtime.prompt_policy.get("system_profile", ""))
        return (
            "[ROLE]\n"
            f"role={runtime.role}\n"
            f"system_profile={system_profile}"
        )

    def _build_tool_section(self, runtime: RuntimeBundle) -> str:
        tool_view = runtime.tool_view
        if tool_view is None:
            return "[TOOLS]\ntool_runtime=internal\nruntime_toolset=(none)\nmodel_visible_tools=(none)"

        system_tools = ",".join(item.name for item in tool_view.system_tools) or "(none)"
        model_tools = [item["function"]["name"] for item in tool_view.model_tools]
        visible = ",".join(model_tools) if model_tools else "(none)"
        return (
            "[TOOLS]\n"
            "tool_runtime=internal\n"
            f"runtime_toolset={system_tools}\n"
            f"model_visible_tools={visible}"
        )

    def _section(self, name: str, source: str, content: str) -> PromptSection:
        return PromptSection(name=name, source=source, content=content)
