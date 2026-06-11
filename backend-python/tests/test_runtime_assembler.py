from uuid import uuid4

from app.config import Settings
from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.runtime_assembler import RuntimeAssembler
from app.runtime.workspace.workspace_resolver import WorkspaceResolver
from app.runtime.workspace.workspace_session import WorkspaceSession


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
            tool_config={
                "tools": [
                    {"name": "plan_tool"},
                    {"name": "delegate_tool"},
                    {"name": "bash_tool"},
                ],
                "auto_tool_choice": True,
            },
        ),
    )
    assert runtime.role == "orchestrator"
    assert set(runtime.tool_registry.tools) == {"plan_tool", "delegate_tool", "bash_tool"}
    assert runtime.instruction_view is not None
    assert runtime.tool_view is not None
    definitions = runtime.tool_registry.get_tool_definitions()
    assert len(definitions) == 3
    assert [item["function"]["name"] for item in definitions] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert runtime.tool_view.model_tools == definitions
    assert runtime.tool_view.tool_choice == "auto"
    assert runtime.tool_view.runtime_tools_enabled is True
    assert runtime.executor_config["provider"] == "openai_compatible"
    assert runtime.workspace_root.endswith("backend-python")
    assert runtime.prompt_policy["system_profile"] == "orchestrator"
    assert [item["name"] for item in runtime.tool_config["tools"]] == ["plan_tool", "delegate_tool", "bash_tool"]


def test_worker_runtime_exposes_code_and_bash_tool_definitions() -> None:
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
            tool_config={
                "tools": [
                    {"name": "code_tool"},
                    {"name": "bash_tool"},
                ],
                "auto_tool_choice": True,
            },
        ),
    )
    assert set(runtime.tool_registry.tools) == {"code_tool", "bash_tool"}
    assert [item["function"]["name"] for item in runtime.tool_view.model_tools] == ["code_tool", "bash_tool"]
    assert runtime.tool_view.tool_choice == "auto"
    assert runtime.tool_view.runtime_tools_enabled is True


def test_runtime_assembler_injects_workspace_session() -> None:
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
            tool_config={
                "tools": [
                    {"name": "code_tool"},
                    {"name": "bash_tool"},
                ],
                "auto_tool_choice": True,
            },
        ),
    )

    assert isinstance(runtime.workspace_session, WorkspaceSession)
    assert str(runtime.workspace_session.workspace_root).endswith("backend-python")


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
            tool_config={
                "tools": [
                    {"name": "plan_tool"},
                    {"name": "delegate_tool"},
                    {"name": "bash_tool"},
                ],
                "auto_tool_choice": True,
            },
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
    assert [item["name"] for item in runtime.tool_config["tools"]] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert runtime.instruction_view is not None
    assert runtime.tool_view is not None
