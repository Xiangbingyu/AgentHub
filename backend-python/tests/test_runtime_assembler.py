from uuid import uuid4

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.runtime_assembler import RuntimeAssembler
from app.runtime.workspace.workspace_resolver import WorkspaceResolver
from app.config import Settings


def _assembler() -> RuntimeAssembler:
    return RuntimeAssembler(
        plan_repository=PlanRepository(),
        workspace_resolver=WorkspaceResolver(Settings(test_workspace_path="E:/Github/AgentHub-weon/backend-python")),
    )


def test_orchestrator_runtime_exposes_tool_registry_contract() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="orchestrator",
            workspace_id=uuid4(),
            root_run_id=run_id,
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        ),
    )
    assert runtime.role == "orchestrator"
    assert set(runtime.tool_registry.tools) == {"plan_tool", "delegate_tool"}
    assert runtime.instruction_view is not None
    assert runtime.tool_view is not None
    definitions = runtime.tool_registry.get_tool_definitions()
    assert len(definitions) == 2
    assert [item["function"]["name"] for item in definitions] == ["plan_tool", "delegate_tool"]
    assert runtime.tool_view.model_tools == definitions
    assert runtime.tool_view.tool_choice == "auto"
    assert runtime.tool_view.runtime_tools_enabled is True
    assert runtime.executor_policy["kind"] == "internal_llm"
    assert runtime.workspace_root.endswith("backend-python")
    assert runtime.prompt_policy["system_profile"] == "orchestrator"
    assert runtime.tool_policy["system_toolset"] == "orchestrator_default"


def test_worker_runtime_keeps_internal_tools_out_of_function_schemas() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="worker",
            workspace_id=uuid4(),
            root_run_id=run_id,
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Worker",
            agent_kind="worker",
        ),
    )
    assert set(runtime.tool_registry.tools) == {"code_tool"}
    assert runtime.tool_view.model_tools == []
    assert runtime.tool_view.tool_choice is None
    assert runtime.tool_view.runtime_tools_enabled is True


def test_orchestrator_runtime_no_longer_forces_plan_tool() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="orchestrator",
            workspace_id=uuid4(),
            root_run_id=run_id,
            status="chatting",
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        ),
    )
    assert runtime.tool_view.tool_choice == "auto"
    assert runtime.tool_view.runtime_tools_enabled is True


def test_runtime_assembler_can_build_runtime_from_run_id() -> None:
    bootstrap_memory_store()
    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    agent = next(item for item in STORE.agents.values() if item.agent_kind == "orchestrator")
    run_id = uuid4()
    agent_run_repository.create(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=run_id,
            status="created",
        )
    )

    assembler = RuntimeAssembler(
        plan_repository=PlanRepository(),
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        workspace_resolver=WorkspaceResolver(Settings(test_workspace_path="E:/Github/AgentHub-weon/backend-python")),
    )

    runtime = assembler.build(run_id)

    assert runtime.agent_run.run_id == run_id
    assert runtime.agent.agent_id == agent.agent_id
    assert runtime.runtime_snapshot["role"] == "orchestrator"
    assert runtime.runtime_snapshot["workspace_root"].endswith("backend-python")
    assert runtime.prompt_policy["system_profile"] == "orchestrator"
    assert runtime.tool_policy["system_toolset"] == "orchestrator_default"
    assert runtime.instruction_view is not None
    assert runtime.tool_view is not None


def test_framework_worker_runtime_defaults_claude_command_without_framework_specific_options() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="worker",
            workspace_id=uuid4(),
            root_run_id=run_id,
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Claude Worker",
            agent_kind="worker",
            executor_policy={"kind": "framework_cli", "framework": "claude"},
        ),
    )

    assert runtime.uses_internal_executor() is False
    assert runtime.executor_policy["command"] == "claude"
    assert runtime.tool_policy["system_toolset"] == "none"
    assert runtime.executor_policy["framework_options"] == {
        "allow_dangerously_skip_permissions": False,
        "dangerously_skip_permissions": False,
    }


def test_framework_worker_runtime_migrates_legacy_executor_fields_into_framework_options() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="worker",
            workspace_id=uuid4(),
            root_run_id=run_id,
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Claude Worker",
            agent_kind="worker",
            executor_policy={
                "kind": "framework_cli",
                "framework": "claude",
                "framework_allowed_tools": ["Read", "Edit"],
                "permission_mode": "bypassPermissions",
            },
        ),
    )

    assert runtime.executor_policy["framework_options"]["allowed_tools"] == ["Read", "Edit"]
    assert runtime.executor_policy["framework_options"]["permission_mode"] == "bypassPermissions"
    assert "framework_allowed_tools" not in runtime.executor_policy
