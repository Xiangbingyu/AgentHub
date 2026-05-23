from uuid import uuid4

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.plan_repository import PlanRepository
from app.runtime.runtime_assembler import RuntimeAssembler


def test_orchestrator_runtime_exposes_tool_registry_contract() -> None:
    assembler = RuntimeAssembler(plan_repository=PlanRepository())
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

    assert set(runtime.toolset) == {"plan_tool", "question_tool", "delegate_tool"}
    definitions = runtime.tool_registry.get_tool_definitions()
    assert len(definitions) == 1
    assert definitions[0]["function"]["name"] == "plan_tool"
    assert runtime.get_llm_tools() == definitions
    assert runtime.get_llm_tool_choice() == {
        "type": "function",
        "function": {"name": "plan_tool"},
    }
    assert runtime.should_dispatch_tool_calls() is True


def test_worker_runtime_keeps_internal_tools_out_of_function_schemas() -> None:
    assembler = RuntimeAssembler(plan_repository=PlanRepository())
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

    assert set(runtime.toolset) == {"code_tool"}
    assert runtime.get_llm_tools() == []
    assert runtime.get_llm_tool_choice() is None
    assert runtime.should_dispatch_tool_calls() is False


def test_created_phase_tool_behavior_is_hidden_behind_runtime_bundle() -> None:
    assembler = RuntimeAssembler(plan_repository=PlanRepository())
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

    assert runtime.get_llm_tool_choice() is None
    assert runtime.should_dispatch_tool_calls() is False


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
    )

    runtime = assembler.build(run_id)

    assert runtime.agent_run.run_id == run_id
    assert runtime.agent.agent_id == agent.agent_id
    assert runtime.prompt_profile == "orchestrator"
