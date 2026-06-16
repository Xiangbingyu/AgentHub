from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from agent_service.app.models.agent import AgentModel
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.runtime.instruction.instruction_resolver import InstructionResolver
from agent_service.app.runtime.mcp.resolver import McpRuntimeResolver
from agent_service.app.runtime.policy.executor_config_resolver import ExecutorConfigResolver
from agent_service.app.runtime.policy.prompt_policy_resolver import PromptPolicyResolver
from agent_service.app.runtime.skills.resolver import SkillRuntimeResolver
from agent_service.app.runtime.policy.tool_config_resolver import ToolConfigResolver
from agent_service.app.runtime.snapshot.runtime_snapshot_resolver import RuntimeSnapshotResolver
from agent_service.app.runtime.tools.tool_registry import ToolRegistry
from agent_service.app.runtime.tools.tool_resolver import ToolResolver
from agent_service.app.runtime.workspace.workspace_resolver import WorkspaceResolver
from agent_service.app.runtime.workspace.workspace_session import WorkspaceSession


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
    # 本回合的协作式中断标志（threading.Event）。工具执行层（如 bash_tool）
    # 轮询它以便在被新消息打断时立即停止，而非等当前调用自然结束。
    cancel_event: Any | None = None

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
        session_workspace_repository: SessionWorkspaceRepository | None = None,
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
        self.session_workspace_repository = (
            session_workspace_repository or SessionWorkspaceRepository()
        )

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
        # 把 run 绑定的 session workspace 磁盘路径注入 snapshot，使 workspace_root
        # 解析到该 session 自己的目录（plan_tool 等据此写 .AgentHub/plans/）。
        # 查不到时不写，交由 WorkspaceResolver 回退到 TEST_WORKSPACE_PATH。
        self._inject_session_workspace_root(agent_run, runtime_snapshot)
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

    def _inject_session_workspace_root(
        self, agent_run: AgentRunModel, runtime_snapshot: dict[str, Any]
    ) -> None:
        # snapshot 已显式带 workspace_root（如测试预置）则尊重，不覆盖。
        if runtime_snapshot.get("workspace_root"):
            return
        workspace = self.session_workspace_repository.get_by_id(agent_run.workspace_id)
        if workspace is not None and workspace.root_path:
            runtime_snapshot["workspace_root"] = workspace.root_path
