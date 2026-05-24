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
from app.runtime.prompt_assembler import PromptAssembler
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
        self.runtime_assembler = RuntimeAssembler(
            plan_repository=PlanRepository(),
            agent_run_repository=agent_run_repository,
            agent_repository=agent_repository,
        )
        self.prompt_assembler = PromptAssembler()
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
        prompt_bundle = self.prompt_assembler.assemble(runtime_bundle, input_event)
        runtime_bundle.prompt_bundle = prompt_bundle
        executor = self.executor_factory.resolve(runtime_bundle)
        if self._is_framework_worker(runtime_bundle):
            self.agent_run_repository.update_status(run_id, "running")

        try:
            llm_response = executor.execute(
                runtime_bundle,
                LlmRequest(
                    system_prompt=prompt_bundle.system_prompt,
                    context_prompt=prompt_bundle.context_prompt,
                    messages=[
                        LlmMessage(role="user", content=self._build_user_message_content(input_event)),
                    ],
                    tools=runtime_bundle.get_llm_tools(),
                    tool_choice=runtime_bundle.get_llm_tool_choice(),
                    model=runtime_bundle.executor_policy.get("model", ""),
                ),
            )
        except Exception as exc:
            if self._is_framework_worker(runtime_bundle):
                self._persist_framework_result(runtime_bundle, status="failed", error=str(exc))
            raise

        if self._is_framework_worker(runtime_bundle):
            self._persist_framework_result(runtime_bundle, status="completed", response=llm_response)
            return AgentRunInputResponse(run_id=run_id, status="accepted")

        runtime_bundle.dispatch_tool_calls(llm_response.tool_calls)
        loop_result = self.loop_engine.run(runtime_bundle, input_event)

        if loop_result.next_status is not None:
            self.agent_run_repository.update_status(run_id, loop_result.next_status)

        return AgentRunInputResponse(run_id=run_id, status="accepted")

    def _is_framework_worker(self, runtime_bundle) -> bool:
        return runtime_bundle.role == "worker" and not runtime_bundle.uses_internal_executor()

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

    def _build_user_message_content(self, input_event: InputEventModel) -> str:
        content = input_event.payload.get("content")
        if isinstance(content, str) and content.strip():
            return content
        return str(input_event.payload)
