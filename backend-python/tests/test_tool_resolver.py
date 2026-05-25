from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.plan_repository import PlanRepository
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_resolver import ToolResolver


def _build_runtime_bundle(
    *,
    role: str,
    tool_policy: dict,
    executor_policy: dict,
) -> RuntimeBundle:
    return RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind=role,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name=f"{role}-agent",
            agent_kind=role,
        ),
        workspace_root="E:/workspace",
        role=role,
        prompt_policy={"system_profile": role},
        tool_policy=tool_policy,
        executor_policy=executor_policy,
    )


def test_tool_resolver_builds_orchestrator_system_tool_view() -> None:
    runtime = _build_runtime_bundle(
        role="orchestrator",
        tool_policy={
            "system_toolset": "orchestrator_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_policy={"kind": "internal_llm"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["plan_tool", "delegate_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["plan_tool", "delegate_tool"]
    assert view.tool_choice == "auto"
    assert "plan_tool" in runtime.tool_registry.tools
    assert "delegate_tool" in runtime.tool_registry.tools


def test_tool_resolver_exposes_framework_capabilities_without_internal_tools() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_policy={"system_toolset": "none", "model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {"allowed_tools": ["Read", "Edit"]},
        },
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert view.system_tools == []
    assert view.model_tools == []
    assert view.framework_capabilities == ["Read", "Edit"]
    assert runtime.tool_registry.tools == {}
