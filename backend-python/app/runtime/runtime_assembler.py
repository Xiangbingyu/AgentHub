from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.plan_repository import PlanRepository
from app.tools.code_tool import CodeTool
from app.tools.delegate_tool import DelegateTool
from app.tools.plan_tool import PlanTool
from app.tools.question_tool import QuestionTool


@dataclass(slots=True)
class RuntimeBundle:
    agent_run: AgentRunModel
    agent: AgentModel
    prompt_profile: str
    toolset: dict[str, object] = field(default_factory=dict)
    prompt_bundle: Any | None = None


class RuntimeAssembler:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self.plan_repository = plan_repository

    def assemble(self, agent_run: AgentRunModel, agent: AgentModel) -> RuntimeBundle:
        if agent.agent_kind == "orchestrator":
            return RuntimeBundle(
                agent_run=agent_run,
                agent=agent,
                prompt_profile="orchestrator",
                toolset={
                    "plan_tool": PlanTool(self.plan_repository),
                    "question_tool": QuestionTool(),
                    "delegate_tool": DelegateTool(),
                },
            )

        return RuntimeBundle(
            agent_run=agent_run,
            agent=agent,
            prompt_profile="worker",
            toolset={
                "code_tool": CodeTool(),
            },
        )
