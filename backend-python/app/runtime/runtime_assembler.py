from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.instruction.instruction_resolver import InstructionResolver
from app.runtime.mcp.resolver import McpRuntimeResolver
from app.runtime.policy.executor_config_resolver import ExecutorConfigResolver
from app.runtime.policy.prompt_policy_resolver import PromptPolicyResolver
from app.runtime.skills.resolver import SkillRuntimeResolver
from app.runtime.policy.tool_config_resolver import ToolConfigResolver
from app.runtime.snapshot.runtime_snapshot_resolver import RuntimeSnapshotResolver
from app.runtime.tools.tool_registry import ToolRegistry
from app.runtime.tools.tool_resolver import ToolResolver
from app.runtime.workspace.workspace_resolver import WorkspaceResolver
from app.runtime.workspace.workspace_session import WorkspaceSession


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
    tool_config: dict[str, Any]
    executor_config: dict[str, Any]
    skill_config: dict[str, Any] = field(default_factory=dict)
    mcp_config: dict[str, Any] = field(default_factory=dict)
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)
    skill_registry: Any | None = None
    mcp_runtime: dict[str, Any] = field(default_factory=dict)
    workspace_session: WorkspaceSession | None = None
    instruction_view: Any | None = None
    tool_view: Any | None = None
    prompt_view: Any | None = None
    runtime_snapshot: dict[str, Any] = field(default_factory=dict)

    def uses_internal_executor(self) -> bool:
        return True


class RuntimeAssembler:
    def __init__(
        self,
        plan_repository: PlanRepository,
        agent_run_repository: AgentRunRepository | None = None,
        agent_repository: AgentRepository | None = None,
        workspace_resolver: WorkspaceResolver | None = None,
        instruction_resolver: InstructionResolver | None = None,
        tool_resolver: ToolResolver | None = None,
        executor_config_resolver: ExecutorConfigResolver | None = None,
        runtime_snapshot_resolver: RuntimeSnapshotResolver | None = None,
        prompt_policy_resolver: PromptPolicyResolver | None = None,
        tool_config_resolver: ToolConfigResolver | None = None,
        skill_runtime_resolver: SkillRuntimeResolver | None = None,
        mcp_runtime_resolver: McpRuntimeResolver | None = None,
    ) -> None:
        self.agent_run_repository = agent_run_repository
        self.agent_repository = agent_repository
        self.workspace_resolver = workspace_resolver or WorkspaceResolver()
        self.instruction_resolver = instruction_resolver or InstructionResolver()
        self.tool_resolver = tool_resolver or ToolResolver(plan_repository)
        self.executor_config_resolver = executor_config_resolver or ExecutorConfigResolver()
        self.runtime_snapshot_resolver = runtime_snapshot_resolver or RuntimeSnapshotResolver()
        self.prompt_policy_resolver = prompt_policy_resolver or PromptPolicyResolver()
        self.tool_config_resolver = tool_config_resolver or ToolConfigResolver()
        self.skill_runtime_resolver = skill_runtime_resolver or SkillRuntimeResolver()
        self.mcp_runtime_resolver = mcp_runtime_resolver or McpRuntimeResolver()

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
        executor_config = self.executor_config_resolver.resolve(runtime_snapshot)
        prompt_policy = self.prompt_policy_resolver.resolve(runtime_snapshot, executor_config=executor_config)
        tool_config = self.tool_config_resolver.resolve(
            runtime_snapshot,
            role=role,
            executor_config=executor_config,
        )
        skill_config = dict(runtime_snapshot.get("skill_config") or {})
        mcp_config = dict(runtime_snapshot.get("mcp_config") or {})
        skill_registry = self.skill_runtime_resolver.resolve(
            workspace_root=workspace_root,
            skill_config=skill_config,
        )
        mcp_runtime = self.mcp_runtime_resolver.resolve(mcp_config)

        runtime_bundle = RuntimeBundle(
            agent_run=agent_run,
            agent=agent,
            workspace_root=workspace_root,
            role=role,
            prompt_policy=prompt_policy,
            tool_config=tool_config,
            skill_config=skill_config,
            mcp_config=mcp_config,
            executor_config=executor_config,
            skill_registry=skill_registry,
            mcp_runtime=mcp_runtime,
            workspace_session=WorkspaceSession(workspace_root),
            runtime_snapshot=runtime_snapshot,
        )
        runtime_bundle.instruction_view = self.instruction_resolver.resolve(runtime_bundle)
        runtime_bundle.tool_view = self.tool_resolver.resolve(runtime_bundle)
        return runtime_bundle
