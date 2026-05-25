from __future__ import annotations

from uuid import UUID

from app.models.input_event import InputEventModel
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.agent_repository import AgentRepository
from app.repositories.input_event_repository import InputEventRepository
from app.repositories.plan_repository import PlanRepository
from app.llm.llm_executor import AgentExecutorFactory
from app.llm.llm_types import LlmMessage, LlmRequest
from app.runtime.loop_engine import LoopEngine
from app.runtime.prompt.prompt_composer import PromptComposer
from app.runtime.runtime_assembler import RuntimeAssembler
from app.schemas.agent_run_input import AgentRunInputRequest, AgentRunInputResponse


class AgentRunInputService:
    def __init__(
        self,
        agent_run_repository: AgentRunRepository,
        agent_repository: AgentRepository,
        input_event_repository: InputEventRepository,
    ) -> None:
        self.agent_run_repository = agent_run_repository
        self.agent_repository = agent_repository
        self.input_event_repository = input_event_repository
        self.plan_repository = PlanRepository()
        self.runtime_assembler = RuntimeAssembler(
            plan_repository=self.plan_repository,
            agent_run_repository=agent_run_repository,
            agent_repository=agent_repository,
        )
        self.prompt_composer = PromptComposer()
        self.executor_factory = AgentExecutorFactory()
        self.loop_engine = LoopEngine(agent_run_repository)

    def input(self, run_id: UUID, payload: AgentRunInputRequest) -> AgentRunInputResponse:
        if self.input_event_repository.get_by_idempotency_key(run_id, payload.idempotency_key) is not None:
            return AgentRunInputResponse(run_id=run_id, status="accepted")

        input_event = InputEventModel(
            input_id=payload.input_id,
            run_id=run_id,
            type=payload.type,
            payload=payload.payload,
            idempotency_key=payload.idempotency_key,
        )
        self.input_event_repository.create(input_event)

        runtime_bundle = self.runtime_assembler.build(run_id)
        self._prepare_run_status(runtime_bundle, input_event)
        runtime_bundle.prompt_view = self.prompt_composer.compose(runtime_bundle, input_event)
        executor = self.executor_factory.resolve(runtime_bundle)

        try:
            llm_response = executor.execute(
                runtime_bundle,
                LlmRequest(
                    system_prompt=runtime_bundle.prompt_view.system_prompt,
                    context_prompt=runtime_bundle.prompt_view.context_prompt,
                    messages=[
                        LlmMessage(role="user", content=self._build_user_message_content(input_event)),
                    ],
                    tools=list(runtime_bundle.tool_view.model_tools),
                    tool_choice=runtime_bundle.tool_view.tool_choice,
                    model=runtime_bundle.executor_policy.get("model", ""),
                ),
            )
        except Exception as exc:
            if self._is_worker_run(runtime_bundle):
                self._persist_worker_failure(runtime_bundle, error=str(exc))
            raise

        if self._is_worker_run(runtime_bundle):
            if runtime_bundle.tool_view.runtime_tools_enabled:
                runtime_bundle.tool_registry.dispatch(runtime_bundle, llm_response.tool_calls)
                refreshed_run = self.agent_run_repository.get_by_id(run_id)
                if refreshed_run is not None:
                    runtime_bundle.agent_run = refreshed_run
            self._persist_worker_success(runtime_bundle, llm_response)
            return AgentRunInputResponse(run_id=run_id, status="accepted")

        if runtime_bundle.tool_view.runtime_tools_enabled:
            runtime_bundle.tool_registry.dispatch(runtime_bundle, llm_response.tool_calls)
            refreshed_run = self.agent_run_repository.get_by_id(run_id)
            if refreshed_run is not None:
                runtime_bundle.agent_run = refreshed_run
        loop_result = self.loop_engine.run(runtime_bundle, input_event)

        if loop_result.next_status is not None:
            self.agent_run_repository.update_status(run_id, loop_result.next_status)

        return AgentRunInputResponse(run_id=run_id, status="accepted")

    def _prepare_run_status(self, runtime_bundle, input_event: InputEventModel) -> None:
        updated_run = None
        if self._is_worker_run(runtime_bundle) and input_event.type.value == "user_input":
            updated_run = self.agent_run_repository.update_status(runtime_bundle.agent_run.run_id, "running")
        elif runtime_bundle.role == "orchestrator" and input_event.type.value == "worker_callback":
            updated_run = self.agent_run_repository.update_status(runtime_bundle.agent_run.run_id, "updating_plan")

        if updated_run is not None:
            runtime_bundle.agent_run = updated_run

    def _is_framework_worker(self, runtime_bundle) -> bool:
        return runtime_bundle.role == "worker" and not runtime_bundle.uses_internal_executor()

    def _is_worker_run(self, runtime_bundle) -> bool:
        return runtime_bundle.role == "worker"

    def _persist_framework_result(self, runtime_bundle, *, status: str, response=None, error: str | None = None) -> None:
        framework_execution = {
            "framework": runtime_bundle.executor_policy.get("framework") or runtime_bundle.executor_policy.get("command"),
            "workspace_root": runtime_bundle.workspace_root,
            "status": status,
        }
        if response is not None:
            framework_execution["content"] = response.content
            framework_execution["raw"] = response.raw
        if error is not None:
            framework_execution["error"] = error

        updated_run = runtime_bundle.agent_run.model_copy(
            update={
                "status": status,
                "context_snapshot": {
                    **runtime_bundle.agent_run.context_snapshot,
                    "framework_execution": framework_execution,
                },
            }
        )
        self.agent_run_repository.update(updated_run)
        runtime_bundle.agent_run = updated_run

    def _persist_internal_worker_result(self, runtime_bundle, response) -> None:
        execution = {
            "kind": "internal_llm",
            "workspace_root": runtime_bundle.workspace_root,
            "status": "completed",
            "content": response.content,
            "raw": response.raw,
            "tool_calls": response.tool_calls,
        }
        updated_run = runtime_bundle.agent_run.model_copy(
            update={
                "status": "completed",
                "context_snapshot": {
                    **runtime_bundle.agent_run.context_snapshot,
                    "worker_execution": execution,
                },
            }
        )
        self.agent_run_repository.update(updated_run)
        runtime_bundle.agent_run = updated_run

    def _persist_worker_success(self, runtime_bundle, response) -> None:
        if self._is_framework_worker(runtime_bundle):
            self._persist_framework_result(runtime_bundle, status="completed", response=response)
            return
        self._persist_internal_worker_result(runtime_bundle, response)

    def _persist_worker_failure(self, runtime_bundle, *, error: str) -> None:
        if self._is_framework_worker(runtime_bundle):
            self._persist_framework_result(runtime_bundle, status="failed", error=error)
            return
        updated_run = runtime_bundle.agent_run.model_copy(
            update={
                "status": "failed",
                "context_snapshot": {
                    **runtime_bundle.agent_run.context_snapshot,
                    "worker_execution": {
                        "kind": "internal_llm",
                        "workspace_root": runtime_bundle.workspace_root,
                        "status": "failed",
                        "error": error,
                    },
                },
            }
        )
        self.agent_run_repository.update(updated_run)
        runtime_bundle.agent_run = updated_run

    def _build_user_message_content(self, input_event: InputEventModel) -> str:
        content = input_event.payload.get("content")
        if isinstance(content, str) and content.strip():
            return content
        return str(input_event.payload)
