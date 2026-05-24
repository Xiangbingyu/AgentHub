from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.tool_registry import ToolRegistry, ToolSpec, default_invoke
from app.runtime.workspace_resolver import WorkspaceResolver
from app.schemas.plan_tool import PlanToolRequest, build_plan_tool_definition
from app.tools.code_tool import CodeTool
from app.tools.plan_tool import PlanTool


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
    prompt_profile: str
    prompt_plan: dict[str, Any]
    tool_plan: dict[str, Any]
    executor_policy: dict[str, Any]
    tool_registry: ToolRegistry
    prompt_bundle: Any | None = None
    runtime_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def toolset(self) -> dict[str, object]:
        return self.tool_registry.tools

    def get_llm_tools(self) -> list[dict[str, Any]]:
        if not self.uses_internal_executor():
            return []
        if not self.tool_plan.get("model_tools_enabled", True):
            return []
        return self.tool_registry.get_tool_definitions()

    def get_llm_tool_choice(self) -> dict[str, Any] | str | None:
        if not self.uses_internal_executor():
            return None
        if not self.get_llm_tools():
            return None
        if self.tool_plan.get("force_tool_name"):
            return {"type": "function", "function": {"name": self.tool_plan["force_tool_name"]}}
        if self.tool_plan.get("auto_tool_choice", False):
            return "auto"
        return None

    def should_dispatch_tool_calls(self) -> bool:
        return (
            self.uses_internal_executor()
            and self.tool_plan.get("runtime_tools_enabled", True)
            and bool(self.get_llm_tools())
        )

    def dispatch_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        if not self.should_dispatch_tool_calls():
            return
        self.tool_registry.dispatch(self, tool_calls)

    def uses_internal_executor(self) -> bool:
        return self.executor_policy.get("kind", "internal_llm") == "internal_llm"


def _invoke_plan_tool(tool: object, runtime: RuntimeBundle, request: PlanToolRequest) -> object:
    return tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        request=request,
    )


def build_runtime_snapshot(agent: AgentModel) -> dict[str, Any]:
    return {
        "role": agent.role,
        "prompt_policy": dict(agent.prompt_policy),
        "tool_policy": dict(agent.tool_policy),
        "executor_policy": dict(agent.executor_policy),
    }


class RuntimeAssembler:
    def __init__(
        self,
        plan_repository: PlanRepository,
        agent_run_repository: AgentRunRepository | None = None,
        agent_repository: AgentRepository | None = None,
        workspace_resolver: WorkspaceResolver | None = None,
    ) -> None:
        self.plan_repository = plan_repository
        self.agent_run_repository = agent_run_repository
        self.agent_repository = agent_repository
        self.workspace_resolver = workspace_resolver or WorkspaceResolver()

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
        runtime_snapshot = self._resolve_runtime_snapshot(agent_run, agent)
        workspace_root = self._resolve_workspace_root(runtime_snapshot)
        role = runtime_snapshot["role"]
        prompt_policy = self._resolve_prompt_policy(runtime_snapshot)
        executor_policy = self._resolve_executor_policy(runtime_snapshot)
        tool_plan, tool_registry = self._build_tool_plan(
            role=role,
            executor_policy=executor_policy,
            runtime_snapshot=runtime_snapshot,
            agent_run=agent_run,
        )

        return RuntimeBundle(
            agent_run=agent_run,
            agent=agent,
            workspace_root=workspace_root,
            role=role,
            prompt_profile=prompt_policy["system_profile"],
            prompt_plan=prompt_policy,
            tool_plan=tool_plan,
            executor_policy=executor_policy,
            tool_registry=tool_registry,
            runtime_snapshot=runtime_snapshot,
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

    def _resolve_runtime_snapshot(self, agent_run: AgentRunModel, agent: AgentModel) -> dict[str, Any]:
        snapshot = dict(agent_run.runtime_snapshot)
        if not snapshot:
            snapshot = build_runtime_snapshot(agent)

        snapshot.setdefault("role", agent.role)
        snapshot.setdefault("prompt_policy", dict(agent.prompt_policy))
        snapshot.setdefault("tool_policy", dict(agent.tool_policy))
        snapshot.setdefault("executor_policy", dict(agent.executor_policy))
        return snapshot

    def _resolve_workspace_root(self, runtime_snapshot: dict[str, Any]) -> str:
        workspace_root = runtime_snapshot.get("workspace_root")
        if workspace_root:
            return str(workspace_root)

        workspace_root = self.workspace_resolver.resolve_root()
        runtime_snapshot["workspace_root"] = workspace_root
        return workspace_root

    def _resolve_prompt_policy(self, runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
        role = runtime_snapshot["role"]
        executor_kind = runtime_snapshot.get("executor_policy", {}).get("kind", "internal_llm")
        default_system_profile = role
        if role == "worker" and executor_kind == "framework_cli":
            default_system_profile = "framework_worker"

        prompt_policy = {
            "system_profile": default_system_profile,
            "include_user_prompt": False,
            "user_prompt": "",
        }
        prompt_policy.update(runtime_snapshot.get("prompt_policy", {}))
        return prompt_policy

    def _resolve_executor_policy(self, runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
        executor_policy = {
            "kind": "internal_llm",
            "provider": "openai_compatible",
            "model": "",
            "framework": None,
            "command": None,
            "timeout_seconds": 300,
            "framework_options": {},
        }
        executor_policy.update(runtime_snapshot.get("executor_policy", {}))
        framework_options = dict(executor_policy.get("framework_options") or {})
        if "allowed_tools" not in framework_options and executor_policy.get("framework_allowed_tools"):
            framework_options["allowed_tools"] = list(executor_policy["framework_allowed_tools"])
        if "permission_mode" not in framework_options and executor_policy.get("permission_mode") is not None:
            framework_options["permission_mode"] = executor_policy["permission_mode"]
        if "allow_dangerously_skip_permissions" not in framework_options:
            framework_options["allow_dangerously_skip_permissions"] = bool(
                executor_policy.get("allow_dangerously_skip_permissions", False)
            )
        if "dangerously_skip_permissions" not in framework_options:
            framework_options["dangerously_skip_permissions"] = bool(
                executor_policy.get("dangerously_skip_permissions", False)
            )
        if executor_policy.get("kind") == "framework_cli" and not executor_policy.get("command"):
            executor_policy["command"] = executor_policy.get("framework") or "claude"
        executor_policy["framework_options"] = framework_options
        executor_policy.pop("framework_allowed_tools", None)
        executor_policy.pop("permission_mode", None)
        executor_policy.pop("allow_dangerously_skip_permissions", None)
        executor_policy.pop("dangerously_skip_permissions", None)
        return executor_policy

    def _build_tool_plan(
        self,
        *,
        role: str,
        executor_policy: dict[str, Any],
        runtime_snapshot: dict[str, Any],
        agent_run: AgentRunModel,
    ) -> tuple[dict[str, Any], ToolRegistry]:
        if executor_policy.get("kind") != "internal_llm":
            return (
                {
                    "system_toolset": "none",
                    "user_tools": [],
                    "model_tools_enabled": False,
                    "runtime_tools_enabled": False,
                    "force_tool_name": None,
                    "auto_tool_choice": False,
                },
                ToolRegistry(),
            )

        configured_tool_policy = dict(runtime_snapshot.get("tool_policy", {}))
        configured_toolset = configured_tool_policy.get("system_toolset")
        if configured_toolset is None:
            configured_toolset = "orchestrator_default" if role == "orchestrator" else "worker_default"

        if configured_toolset == "orchestrator_default":
            registry = self._build_orchestrator_tool_registry()
        elif configured_toolset == "worker_default":
            registry = self._build_worker_tool_registry()
        else:
            registry = ToolRegistry()

        force_plan_tool = (
            role == "orchestrator"
            and configured_toolset == "orchestrator_default"
            and agent_run.status == "created"
            and self._needs_initial_plan(agent_run.run_id)
        )

        return (
            {
                "system_toolset": configured_toolset,
                "user_tools": configured_tool_policy.get("user_tools", []),
                "model_tools_enabled": configured_tool_policy.get("model_tools_enabled", True),
                "runtime_tools_enabled": configured_tool_policy.get("runtime_tools_enabled", True),
                "force_tool_name": "plan_tool" if force_plan_tool else None,
                "auto_tool_choice": role == "orchestrator" and configured_toolset == "orchestrator_default",
            },
            registry,
        )

    def _needs_initial_plan(self, run_id: UUID) -> bool:
        plan = self.plan_repository.get_by_run_id(run_id)
        if plan is None:
            return True
        return not bool(plan.raw_document.strip())
