from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.repositories.plan_repository import PlanRepository
from app.schemas.delegate_tool import DelegateToolRequest, build_delegate_tool_definition
from app.runtime.tools.tool_registry import ToolRegistry, ToolSpec, default_invoke
from app.schemas.plan_tool import PlanToolRequest, build_plan_tool_definition
from app.tools.code_tool import CodeTool
from app.tools.delegate_tool import DelegateTool
from app.tools.plan_tool import PlanTool

if TYPE_CHECKING:
    from app.runtime.runtime_assembler import RuntimeBundle


@dataclass(slots=True)
class ToolItem:
    name: str
    source: str
    definition: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolView:
    system_toolset: str
    system_tools: list[ToolItem] = field(default_factory=list)
    custom_tools: list[dict[str, Any]] = field(default_factory=list)
    framework_capabilities: list[str] = field(default_factory=list)
    model_tools: list[dict[str, Any]] = field(default_factory=list)
    model_tools_enabled: bool = False
    runtime_tools_enabled: bool = False
    tool_choice: dict[str, Any] | str | None = None


def _invoke_plan_tool(tool: object, runtime: RuntimeBundle, request: PlanToolRequest) -> object:
    return tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        request=request,
    )


def _invoke_delegate_tool(tool: object, runtime: RuntimeBundle, request: DelegateToolRequest) -> object:
    return tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        request=request,
    )


class ToolResolver:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self.plan_repository = plan_repository

    def resolve(self, runtime: RuntimeBundle) -> ToolView:
        if not runtime.uses_internal_executor():
            runtime.tool_registry = ToolRegistry()
            capabilities = list(runtime.executor_policy.get("framework_options", {}).get("allowed_tools") or [])
            return ToolView(
                system_toolset="none",
                custom_tools=list(runtime.tool_policy.get("user_tools", [])),
                framework_capabilities=capabilities,
                model_tools_enabled=False,
                runtime_tools_enabled=False,
            )

        system_toolset = str(runtime.tool_policy.get("system_toolset") or "none")
        registry = self._build_registry(system_toolset)
        runtime.tool_registry = registry
        model_tools_enabled = bool(runtime.tool_policy.get("model_tools_enabled", True))
        runtime_tools_enabled = bool(runtime.tool_policy.get("runtime_tools_enabled", True))
        model_tools = registry.get_tool_definitions() if model_tools_enabled else []
        tool_choice: dict[str, Any] | str | None = None
        if model_tools and runtime.tool_policy.get("auto_tool_choice", False):
            tool_choice = "auto"

        return ToolView(
            system_toolset=system_toolset,
            system_tools=[
                ToolItem(name=spec.name, source="system", definition=spec.definition)
                for spec in registry.specs.values()
            ],
            custom_tools=list(runtime.tool_policy.get("user_tools", [])),
            model_tools=model_tools,
            model_tools_enabled=model_tools_enabled,
            runtime_tools_enabled=runtime_tools_enabled,
            tool_choice=tool_choice,
        )

    def _build_registry(self, system_toolset: str) -> ToolRegistry:
        registry = ToolRegistry()
        if system_toolset == "orchestrator_default":
            registry.register(
                ToolSpec(
                    name="plan_tool",
                    tool=PlanTool(self.plan_repository),
                    definition=build_plan_tool_definition(),
                    request_model=PlanToolRequest,
                    invoke=_invoke_plan_tool,
                )
            )
            registry.register(
                ToolSpec(
                    name="delegate_tool",
                    tool=DelegateTool(),
                    definition=build_delegate_tool_definition(),
                    request_model=DelegateToolRequest,
                    invoke=_invoke_delegate_tool,
                )
            )
            return registry

        if system_toolset == "worker_default":
            registry.register(
                ToolSpec(
                    name="code_tool",
                    tool=CodeTool(),
                    invoke=default_invoke,
                )
            )
        return registry
