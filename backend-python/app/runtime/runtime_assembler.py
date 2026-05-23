from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.tool_registry import ToolRegistry, ToolSpec, default_invoke
from app.schemas.plan_tool import PlanToolRequest, build_plan_tool_definition
from app.tools.code_tool import CodeTool
from app.tools.delegate_tool import DelegateTool
from app.tools.plan_tool import PlanTool
from app.tools.question_tool import QuestionTool


@dataclass(slots=True)
class RuntimeContext:
    agent_run: AgentRunModel
    agent: AgentModel


@dataclass(slots=True)
class RuntimeBundle:
    agent_run: AgentRunModel
    agent: AgentModel
    prompt_profile: str
    tool_registry: ToolRegistry
    prompt_bundle: Any | None = None

    @property
    def toolset(self) -> dict[str, object]:
        return self.tool_registry.tools

    def get_llm_tools(self) -> list[dict[str, Any]]:
        return self.tool_registry.get_tool_definitions()

    def get_llm_tool_choice(self) -> dict[str, Any] | None:
        if self.agent_run.status != "created":
            return None
        return self.tool_registry.get_default_tool_choice()

    def should_dispatch_tool_calls(self) -> bool:
        return self.agent_run.status == "created" and self.get_llm_tool_choice() is not None

    def dispatch_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        if not self.should_dispatch_tool_calls():
            return
        self.tool_registry.dispatch(self, tool_calls)


def _invoke_plan_tool(tool: object, runtime: RuntimeBundle, request: PlanToolRequest) -> object:
    return tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        request=request,
    )


class RuntimeAssembler:
    def __init__(
        self,
        plan_repository: PlanRepository,
        agent_run_repository: AgentRunRepository | None = None,
        agent_repository: AgentRepository | None = None,
    ) -> None:
        self.plan_repository = plan_repository
        self.agent_run_repository = agent_run_repository
        self.agent_repository = agent_repository

    def resolve(self, run_id: UUID) -> RuntimeContext:
        if self.agent_run_repository is None or self.agent_repository is None:
            raise ValueError("agent_run_repository and agent_repository are required to resolve runtime")

        agent_run = self.agent_run_repository.get_by_id(run_id)
        if agent_run is None:
            raise ValueError("run not found")

        agent = self.agent_repository.get_by_id(agent_run.agent_id)
        if agent is None:
            raise ValueError("agent not found")

        return RuntimeContext(agent_run=agent_run, agent=agent)

    def build(self, run_id: UUID) -> RuntimeBundle:
        runtime = self.resolve(run_id)
        return self.assemble(runtime.agent_run, runtime.agent)

    def assemble(self, agent_run: AgentRunModel, agent: AgentModel) -> RuntimeBundle:
        if agent.agent_kind == "orchestrator":
            return RuntimeBundle(
                agent_run=agent_run,
                agent=agent,
                prompt_profile="orchestrator",
                tool_registry=self._build_orchestrator_tool_registry(),
            )

        return RuntimeBundle(
            agent_run=agent_run,
            agent=agent,
            prompt_profile="worker",
            tool_registry=self._build_worker_tool_registry(),
        )

    def _build_orchestrator_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="plan_tool",
                tool=PlanTool(self.plan_repository),
                definition=build_plan_tool_definition(),
                request_model=PlanToolRequest,
                invoke=_invoke_plan_tool,
                default_tool_choice=True,
            )
        )
        registry.register(
            ToolSpec(
                name="question_tool",
                tool=QuestionTool(),
                invoke=default_invoke,
            )
        )
        registry.register(
            ToolSpec(
                name="delegate_tool",
                tool=DelegateTool(),
                invoke=default_invoke,
            )
        )
        return registry

    def _build_worker_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="code_tool",
                tool=CodeTool(),
                invoke=default_invoke,
            )
        )
        return registry
