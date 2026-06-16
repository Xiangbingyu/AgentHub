from uuid import uuid4

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.repositories.subtask_repository import SubtaskRepository
from agent_service.app.schemas.agent_run_input import AgentRunInputResponse, InputEventType
from agent_service.app.schemas.delegate_tool import DelegateToolRequest
from agent_service.app.tools.delegate_tool import DelegateTool


class RecordingRunInputService:
    def __init__(self, agent_run_repository: AgentRunRepository) -> None:
        self.agent_run_repository = agent_run_repository
        self.calls = []

    def input(self, run_id, payload):
        self.calls.append((run_id, payload))
        agent_run = self.agent_run_repository.get_by_id(run_id)
        if agent_run is not None and agent_run.agent_kind == "worker" and payload.type == InputEventType.user_input:
            updated = agent_run.model_copy(
                update={
                    "status": "completed",
                    "context_snapshot": {
                        **agent_run.context_snapshot,
                        "framework_execution": {
                            "status": "completed",
                            "content": "worker finished delegated task",
                        },
                    },
                }
            )
            self.agent_run_repository.update(updated)
        return AgentRunInputResponse(run_id=run_id, status="accepted")


def test_delegate_tool_creates_worker_run_and_emits_parent_callback() -> None:
    bootstrap_memory_store()
    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    subtask_repository = SubtaskRepository()
    plan_repository = PlanRepository()

    orchestrator_agent = next(agent for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    worker_agent = next(agent for agent in STORE.agents.values() if agent.agent_kind == "worker")
    parent_run_id = uuid4()
    parent_run = AgentRunModel(
        run_id=parent_run_id,
        agent_id=orchestrator_agent.agent_id,
        role="orchestrator",
        agent_kind="orchestrator",
        workspace_id=uuid4(),
        root_run_id=parent_run_id,
        status="chatting",
    )
    agent_run_repository.create(parent_run)

    service = RecordingRunInputService(agent_run_repository)
    tool = DelegateTool(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
        input_event_repository=input_event_repository,
        subtask_repository=subtask_repository,
        plan_repository=plan_repository,
        run_input_service_factory=lambda: service,
        async_runner=lambda job: job(),
    )

    response = tool.run(
        run_id=parent_run.run_id,
        workspace_id=parent_run.workspace_id,
        request=DelegateToolRequest(
            worker_agent_id=worker_agent.agent_id,
            task_prompt="Please implement the delegated worker task.",
            summary="delegated to worker",
        ),
    )

    assert response.status == "accepted"
    assert response.summary == "delegated to worker"

    subtask = subtask_repository.get_by_id(response.subtask_id)
    worker_run = agent_run_repository.get_by_id(response.worker_run_id)
    parent_after_delegate = agent_run_repository.get_by_id(parent_run.run_id)
    assert subtask is not None
    assert worker_run is not None
    assert parent_after_delegate is not None
    assert parent_after_delegate.status == "waiting_callback"
    assert parent_after_delegate.context_snapshot["last_delegate"]["subtask_id"] == str(subtask.subtask_id)
    assert subtask.parent_run_id == parent_run.run_id
    assert subtask.worker_run_id == worker_run.run_id
    assert subtask.status == "completed"
    assert subtask.result_ref == str(worker_run.run_id)
    assert worker_run.parent_run_id == parent_run.run_id
    assert worker_run.root_run_id == parent_run.root_run_id
    assert worker_run.agent_id == worker_agent.agent_id
    assert len(service.calls) == 2
    assert service.calls[0][0] == worker_run.run_id
    assert service.calls[0][1].type == InputEventType.user_input
    assert service.calls[1][0] == parent_run.run_id
    assert service.calls[1][1].type == InputEventType.worker_callback
    callback_payload = service.calls[1][1].payload
    assert callback_payload["subtask_id"] == str(subtask.subtask_id)
    assert callback_payload["worker_run_id"] == str(worker_run.run_id)
    assert callback_payload["status"] == "completed"
    assert "worker finished delegated task" in callback_payload["content"]


def test_delegate_tool_marks_parent_failed_when_callback_delivery_fails() -> None:
    bootstrap_memory_store()
    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    subtask_repository = SubtaskRepository()
    plan_repository = PlanRepository()

    orchestrator_agent = next(agent for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    worker_agent = next(agent for agent in STORE.agents.values() if agent.agent_kind == "worker")
    parent_run_id = uuid4()
    parent_run = AgentRunModel(
        run_id=parent_run_id,
        agent_id=orchestrator_agent.agent_id,
        role="orchestrator",
        agent_kind="orchestrator",
        workspace_id=uuid4(),
        root_run_id=parent_run_id,
        status="chatting",
    )
    agent_run_repository.create(parent_run)

    class FailingCallbackService(RecordingRunInputService):
        def input(self, run_id, payload):
            if payload.type == InputEventType.worker_callback:
                raise RuntimeError("callback delivery failed")
            return super().input(run_id, payload)

    service = FailingCallbackService(agent_run_repository)
    tool = DelegateTool(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
        input_event_repository=input_event_repository,
        subtask_repository=subtask_repository,
        plan_repository=plan_repository,
        run_input_service_factory=lambda: service,
        async_runner=lambda job: job(),
    )

    response = tool.run(
        run_id=parent_run.run_id,
        workspace_id=parent_run.workspace_id,
        request=DelegateToolRequest(
            worker_agent_id=worker_agent.agent_id,
            task_prompt="Please implement the delegated worker task.",
            summary="delegated to worker",
        ),
    )

    updated_parent = agent_run_repository.get_by_id(parent_run.run_id)
    assert response.status == "accepted"
    assert updated_parent is not None
    assert updated_parent.status == "failed"
    assert updated_parent.context_snapshot["last_delegate_error"]["error"] == "callback delivery failed"
