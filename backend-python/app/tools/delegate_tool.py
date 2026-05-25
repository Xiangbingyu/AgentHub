from __future__ import annotations

import threading
from uuid import UUID, uuid4

from app.models.agent_run import AgentRunModel
from app.models.subtask import SubtaskModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subtask_repository import SubtaskRepository
from app.runtime.snapshot.runtime_snapshot_resolver import RuntimeSnapshotResolver
from app.schemas.agent_run_input import AgentRunInputRequest, InputEventType
from app.schemas.delegate_tool import DelegateToolRequest, DelegateToolResponse


class DelegateTool:
    def __init__(
        self,
        agent_repository: AgentRepository | None = None,
        agent_run_repository: AgentRunRepository | None = None,
        input_event_repository: InputEventRepository | None = None,
        subtask_repository: SubtaskRepository | None = None,
        plan_repository: PlanRepository | None = None,
        runtime_snapshot_resolver: RuntimeSnapshotResolver | None = None,
        run_input_service_factory=None,
        async_runner=None,
    ) -> None:
        self.agent_repository = agent_repository or AgentRepository()
        self.agent_run_repository = agent_run_repository or AgentRunRepository()
        self.input_event_repository = input_event_repository or InputEventRepository()
        self.subtask_repository = subtask_repository or SubtaskRepository()
        self.plan_repository = plan_repository or PlanRepository()
        self.runtime_snapshot_resolver = runtime_snapshot_resolver or RuntimeSnapshotResolver()
        self.run_input_service_factory = run_input_service_factory or self._build_run_input_service
        self.async_runner = async_runner or self._run_async

    def run(self, *, run_id: UUID, workspace_id: UUID, request: DelegateToolRequest) -> DelegateToolResponse:
        parent_run = self.agent_run_repository.get_by_id(run_id)
        if parent_run is None:
            raise ValueError("parent run not found")

        worker_agent = self.agent_repository.get_by_id(request.worker_agent_id)
        if worker_agent is None:
            raise ValueError("worker agent not found")
        if worker_agent.agent_kind != "worker":
            raise ValueError("delegate_tool requires a worker agent")

        worker_run_id = uuid4()
        subtask_id = uuid4()
        root_run_id = parent_run.root_run_id or parent_run.run_id
        worker_run = AgentRunModel(
            run_id=worker_run_id,
            agent_id=worker_agent.agent_id,
            role=worker_agent.role,
            agent_kind=worker_agent.agent_kind,
            workspace_id=workspace_id,
            parent_run_id=parent_run.run_id,
            root_run_id=root_run_id,
            status="created",
            context_snapshot={
                "delegated_by_run_id": str(parent_run.run_id),
                "subtask_id": str(subtask_id),
            },
            runtime_snapshot=self.runtime_snapshot_resolver.build_default_snapshot(worker_agent),
        )
        self.agent_run_repository.create(worker_run)

        subtask = SubtaskModel(
            subtask_id=subtask_id,
            root_run_id=root_run_id,
            parent_run_id=parent_run.run_id,
            worker_run_id=worker_run_id,
            status="queued",
            task_prompt=request.task_prompt,
        )
        self.subtask_repository.create(subtask)
        self.agent_run_repository.update(
            parent_run.model_copy(
                update={
                    "status": "waiting_callback",
                    "context_snapshot": {
                        **parent_run.context_snapshot,
                        "last_delegate": {
                            "subtask_id": str(subtask_id),
                            "worker_run_id": str(worker_run_id),
                            "worker_agent_id": str(worker_agent.agent_id),
                            "task_prompt": request.task_prompt,
                        },
                    },
                }
            )
        )

        self.async_runner(
            lambda: self._execute_worker(
                parent_run_id=parent_run.run_id,
                subtask_id=subtask_id,
                worker_run_id=worker_run_id,
                task_prompt=request.task_prompt,
            )
        )

        summary = request.summary.strip() or "Worker task delegated and scheduled in background."
        return DelegateToolResponse(
            subtask_id=subtask_id,
            worker_run_id=worker_run_id,
            status="accepted",
            summary=summary,
        )

    def _build_run_input_service(self):
        from app.services.agent_run_input_service import AgentRunInputService

        return AgentRunInputService(
            agent_run_repository=self.agent_run_repository,
            agent_repository=self.agent_repository,
            input_event_repository=self.input_event_repository,
        )

    def _run_async(self, job) -> None:
        thread = threading.Thread(target=job, daemon=True)
        thread.start()

    def _execute_worker(
        self,
        *,
        parent_run_id: UUID,
        subtask_id: UUID,
        worker_run_id: UUID,
        task_prompt: str,
    ) -> None:
        self.subtask_repository.update_status(subtask_id, "running")
        worker_run = self.agent_run_repository.get_by_id(worker_run_id)
        if worker_run is not None:
            self.agent_run_repository.update(worker_run.model_copy(update={"status": "running"}))
        service = self.run_input_service_factory()
        callback_payload = {
            "content": (
                "Worker task completed.\n"
                f"subtask_id={subtask_id}\n"
                f"worker_run_id={worker_run_id}\n"
            ),
            "subtask_id": str(subtask_id),
            "worker_run_id": str(worker_run_id),
            "task_prompt": task_prompt,
            "status": "completed",
        }

        try:
            service.input(
                run_id=worker_run_id,
                payload=AgentRunInputRequest(
                    input_id=uuid4(),
                    type=InputEventType.user_input,
                    payload={"content": task_prompt},
                    idempotency_key=f"delegate-worker:{subtask_id}",
                ),
            )
            worker_run = self.agent_run_repository.get_by_id(worker_run_id)
            worker_status = worker_run.status if worker_run is not None else "completed"
            result_content = self._extract_worker_result(worker_run_id)
            callback_payload["status"] = worker_status
            callback_payload["content"] = (
                "Worker task completed.\n"
                f"subtask_id={subtask_id}\n"
                f"worker_run_id={worker_run_id}\n"
                f"status={worker_status}\n"
                f"result={result_content}"
            )
            callback_payload["result"] = result_content
            self.subtask_repository.update(
                self.subtask_repository.get_by_id(subtask_id).model_copy(
                    update={
                        "status": "completed" if worker_status != "failed" else "failed",
                        "result_ref": str(worker_run_id),
                    }
                )
            )
        except Exception as exc:
            callback_payload["status"] = "failed"
            callback_payload["content"] = (
                "Worker task failed.\n"
                f"subtask_id={subtask_id}\n"
                f"worker_run_id={worker_run_id}\n"
                f"error={exc}"
            )
            callback_payload["error"] = str(exc)
            self.subtask_repository.update(
                self.subtask_repository.get_by_id(subtask_id).model_copy(
                    update={"status": "failed"}
                )
            )

        try:
            service.input(
                run_id=parent_run_id,
                payload=AgentRunInputRequest(
                    input_id=uuid4(),
                    type=InputEventType.worker_callback,
                    payload=callback_payload,
                    idempotency_key=f"delegate-callback:{subtask_id}",
                ),
            )
        except Exception as exc:
            parent_run = self.agent_run_repository.get_by_id(parent_run_id)
            if parent_run is not None:
                self.agent_run_repository.update(
                    parent_run.model_copy(
                        update={
                            "status": "failed",
                            "context_snapshot": {
                                **parent_run.context_snapshot,
                                "last_delegate_error": {
                                    "subtask_id": str(subtask_id),
                                    "worker_run_id": str(worker_run_id),
                                    "error": str(exc),
                                },
                            },
                        }
                    )
                )

    def _extract_worker_result(self, worker_run_id: UUID) -> str:
        worker_run = self.agent_run_repository.get_by_id(worker_run_id)
        if worker_run is None:
            return ""
        for key in ("framework_execution", "worker_execution"):
            execution = worker_run.context_snapshot.get(key, {})
            if not isinstance(execution, dict):
                continue
            content = execution.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return ""
