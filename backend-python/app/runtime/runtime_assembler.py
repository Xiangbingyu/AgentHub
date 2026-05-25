from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.executor.executor_policy_resolver import ExecutorPolicyResolver
from app.runtime.instruction.instruction_resolver import InstructionResolver
from app.runtime.policy.prompt_policy_resolver import PromptPolicyResolver
from app.runtime.policy.tool_policy_resolver import ToolPolicyResolver
from app.runtime.snapshot.runtime_snapshot_resolver import RuntimeSnapshotResolver
from app.runtime.tools.tool_registry import ToolRegistry
from app.runtime.tools.tool_resolver import ToolResolver
from app.runtime.workspace.workspace_resolver import WorkspaceResolver


@dataclass(slots=True)
class RuntimeContext:
    agent_run: AgentRunModel
    agent: AgentModel


@dataclass(slots=True)
class RuntimeBundle:
    agent_run: AgentRunModel
    agent: AgentModel
    workspace_root: str
    role: str
    prompt_policy: dict[str, Any]
    tool_policy: dict[str, Any]
    executor_policy: dict[str, Any]
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)
    instruction_view: Any | None = None
    tool_view: Any | None = None
    prompt_view: Any | None = None
    runtime_snapshot: dict[str, Any] = field(default_factory=dict)

    def uses_internal_executor(self) -> bool:
        return self.executor_policy.get("kind", "internal_llm") == "internal_llm"


class RuntimeAssembler:
    def __init__(
        self,
        plan_repository: PlanRepository,
        agent_run_repository: AgentRunRepository | None = None,
        agent_repository: AgentRepository | None = None,
        workspace_resolver: WorkspaceResolver | None = None,
        instruction_resolver: InstructionResolver | None = None,
        tool_resolver: ToolResolver | None = None,
        executor_policy_resolver: ExecutorPolicyResolver | None = None,
        runtime_snapshot_resolver: RuntimeSnapshotResolver | None = None,
        prompt_policy_resolver: PromptPolicyResolver | None = None,
        tool_policy_resolver: ToolPolicyResolver | None = None,
    ) -> None:
        self.agent_run_repository = agent_run_repository
        self.agent_repository = agent_repository
        self.workspace_resolver = workspace_resolver or WorkspaceResolver()
        self.instruction_resolver = instruction_resolver or InstructionResolver()
        self.tool_resolver = tool_resolver or ToolResolver(plan_repository)
        self.executor_policy_resolver = executor_policy_resolver or ExecutorPolicyResolver()
        self.runtime_snapshot_resolver = runtime_snapshot_resolver or RuntimeSnapshotResolver()
        self.prompt_policy_resolver = prompt_policy_resolver or PromptPolicyResolver()
        self.tool_policy_resolver = tool_policy_resolver or ToolPolicyResolver()

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
        runtime_snapshot = self.runtime_snapshot_resolver.resolve(agent_run, agent)
        workspace_root = self.workspace_resolver.resolve(runtime_snapshot)
        role = runtime_snapshot["role"]
        executor_policy = self.executor_policy_resolver.resolve(runtime_snapshot)
        prompt_policy = self.prompt_policy_resolver.resolve(runtime_snapshot, executor_policy=executor_policy)
        tool_policy = self.tool_policy_resolver.resolve(
            runtime_snapshot,
            role=role,
            executor_policy=executor_policy,
        )

        runtime_bundle = RuntimeBundle(
            agent_run=agent_run,
            agent=agent,
            workspace_root=workspace_root,
            role=role,
            prompt_policy=prompt_policy,
            tool_policy=tool_policy,
            executor_policy=executor_policy,
            runtime_snapshot=runtime_snapshot,
        )
        runtime_bundle.instruction_view = self.instruction_resolver.resolve(runtime_bundle)
        runtime_bundle.tool_view = self.tool_resolver.resolve(runtime_bundle)
        return runtime_bundle
