from pathlib import Path
from uuid import uuid4

from app.llm.llm_types import LlmResponse
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.plan_repository import PlanRepository
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.schemas.agent_run_input import AgentRunInputRequest
from app.services.agent_run_input_service import AgentRunInputService


class StaticExecutor:
    def __init__(self, response: LlmResponse) -> None:
        self.response = response

    def execute(self, runtime, request) -> LlmResponse:
        return self.response


class SequencedExecutor:
    def __init__(self, responses: list[LlmResponse]) -> None:
        self.responses = responses
        self.requests = []

    def execute(self, runtime, request) -> LlmResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("no response prepared for executor")
        return self.responses.pop(0)


def _build_service() -> tuple[AgentRunInputService, AgentRepository, AgentRunRepository]:
    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    return service, agent_repository, agent_run_repository


def test_worker_callback_moves_orchestrator_to_completed() -> None:
    service, agent_repository, agent_run_repository = _build_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        )
    )
    run = agent_run_repository.create(
        AgentRunModel(
            run_id=uuid4(),
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
            status="waiting_callback",
            runtime_snapshot={"role": "orchestrator"},
        )
    )
    service.executor_factory.resolve = lambda runtime: StaticExecutor(LlmResponse(content="updated", tool_calls=[], raw={}))

    response = service.input(
        run.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="worker_callback",
            payload={"summary": "worker completed", "status": "completed"},
            idempotency_key=str(uuid4()),
        ),
    )

    updated_run = agent_run_repository.get_by_id(run.run_id)
    assert response.status == "accepted"
    assert updated_run is not None
    assert updated_run.status == "completed"


def test_internal_worker_input_marks_run_completed_and_persists_result() -> None:
    service, agent_repository, agent_run_repository = _build_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Worker",
            agent_kind="worker",
        )
    )
    run = agent_run_repository.create(
        AgentRunModel(
            run_id=uuid4(),
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
            runtime_snapshot={"role": "worker"},
        )
    )
    service.executor_factory.resolve = lambda runtime: StaticExecutor(
        LlmResponse(content="worker finished task", tool_calls=[], raw={"provider": "test"})
    )

    response = service.input(
        run.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "finish delegated work"},
            idempotency_key=str(uuid4()),
        ),
    )

    updated_run = agent_run_repository.get_by_id(run.run_id)
    assert response.status == "accepted"
    assert updated_run is not None
    assert updated_run.status == "completed"
    assert updated_run.context_snapshot["worker_execution"]["content"] == "worker finished task"
    assert updated_run.context_snapshot["worker_execution"]["status"] == "completed"


def test_internal_worker_dispatches_tool_calls_before_persisting_success() -> None:
    service, agent_repository, agent_run_repository = _build_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Worker",
            agent_kind="worker",
        )
    )
    run = agent_run_repository.create(
        AgentRunModel(
            run_id=uuid4(),
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
            runtime_snapshot={
                "role": "worker",
                "tool_policy": {
                    "system_toolset": "worker_default",
                    "model_tools_enabled": False,
                    "runtime_tools_enabled": True,
                },
            },
        )
    )
    service.executor_factory.resolve = lambda runtime: StaticExecutor(
        LlmResponse(
            content="worker used code tool",
            tool_calls=[
                {
                    "id": "tool_1",
                    "type": "function",
                    "function": {
                        "name": "code_tool",
                        "arguments": '{"action":"list_files","path":"."}',
                    },
                }
            ],
            raw={"provider": "test"},
        )
    )

    called = {}

    def record_call(*, run_id, workspace_id, runtime, arguments):
        called["run_id"] = run_id
        called["workspace_id"] = workspace_id
        called["runtime"] = runtime
        called["arguments"] = arguments
        return None

    runtime_bundle = service.runtime_assembler.build(run.run_id)
    runtime_bundle.tool_registry.tools["code_tool"].run = record_call
    service.runtime_assembler.build = lambda _run_id: runtime_bundle

    response = service.input(
        run.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "finish delegated work"},
            idempotency_key=str(uuid4()),
        ),
    )

    updated_run = agent_run_repository.get_by_id(run.run_id)
    assert response.status == "accepted"
    assert called["run_id"] == run.run_id
    assert called["workspace_id"] == run.workspace_id
    assert called["runtime"] is runtime_bundle
    assert called["arguments"].action == "list_files"
    assert called["arguments"].path == "."
    assert updated_run is not None
    assert updated_run.status == "completed"


def test_create_run_does_not_create_plan_until_plan_tool_is_used() -> None:
    service, agent_repository, agent_run_repository = _build_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        )
    )
    from app.services.agent_run_create_service import AgentRunCreateService
    from app.schemas.agent_run_create import AgentRunCreateRequest

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    create_response = create_service.create_run(
        AgentRunCreateRequest(
            agent_id=agent.agent_id,
            workspace_id=uuid4(),
            metadata={},
        )
    )

    assert PlanRepository().get_by_run_id(create_response.run_id) is None


def test_internal_orchestrator_continues_after_tool_call_to_reach_plan_tool() -> None:
    service, agent_repository, agent_run_repository = _build_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        )
    )
    run = agent_run_repository.create(
        AgentRunModel(
            run_id=uuid4(),
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
            runtime_snapshot={"role": "orchestrator"},
        )
    )
    executor = SequencedExecutor(
        [
            LlmResponse(
                content="inspect first",
                tool_calls=[
                    {
                        "id": "tool_1",
                        "type": "function",
                        "function": {
                            "name": "bash_tool",
                            "arguments": '{"command":"Get-ChildItem -LiteralPath .AgentHub/tests/test1","description":"Lists delegated test directory"}',
                        },
                    }
                ],
                raw={"provider": "test"},
            ),
            LlmResponse(
                content="plan updated",
                tool_calls=[
                    {
                        "id": "tool_2",
                        "type": "function",
                        "function": {
                            "name": "plan_tool",
                            "arguments": (
                                '{"plan":{"title":"Inspect file","goal":"Inspect workspace before planning",'
                                '"summary":"Inspection recorded","steps":[{"step_id":"1",'
                                '"content":"Inspect delegated test directory","status":"completed","priority":"high"}]}}'
                            ),
                        },
                    }
                ],
                raw={"provider": "test"},
            ),
            LlmResponse(
                content="inspection and planning complete",
                tool_calls=[],
                raw={"provider": "test"},
            ),
        ]
    )
    service.executor_factory.resolve = lambda runtime: executor

    response = service.input(
        run.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "Inspect the delegated test directory and then create the plan."},
            idempotency_key=str(uuid4()),
        ),
    )

    updated_run = agent_run_repository.get_by_id(run.run_id)
    plan = PlanRepository().get_by_run_id(run.run_id)
    assert response.status == "accepted"
    assert updated_run is not None
    assert plan is not None
    assert plan.status == "completed"
    assert Path(plan.file_path).exists()
    assert len(executor.requests) == 3
