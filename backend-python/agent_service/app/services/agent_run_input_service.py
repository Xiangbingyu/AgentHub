from __future__ import annotations

import json

from uuid import UUID, uuid4

from agent_service.app.models.domain_event import DomainEventModel
from agent_service.app.models.input_event import InputEventModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.llm.llm_executor import InternalLlmExecutor
from agent_service.app.llm.llm_types import LlmMessage, LlmRequest
from agent_service.app.runtime.loop_engine import LoopEngine
from agent_service.app.runtime.prompt.prompt_composer import PromptComposer
from agent_service.app.runtime.runtime_assembler import RuntimeAssembler
from agent_service.app.schemas.agent_run_input import AgentRunInputRequest, AgentRunInputResponse
from agent_service.app.services.domain_event_emitter import DomainEventEmitter


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
        self.domain_event_repository = DomainEventRepository()
        self.domain_event_emitter = DomainEventEmitter(self.domain_event_repository)
        self.runtime_assembler = RuntimeAssembler(
            plan_repository=self.plan_repository,
            agent_run_repository=agent_run_repository,
            agent_repository=agent_repository,
        )
        self.prompt_composer = PromptComposer()
        self.executor = InternalLlmExecutor()
        self.executor_factory = lambda runtime: self.executor
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
        self._persist_domain_event(runtime_bundle, input_event)
        self._prepare_run_status(runtime_bundle, input_event)
        self._emit_run_started(runtime_bundle)
        runtime_bundle.prompt_view = self.prompt_composer.compose(runtime_bundle, input_event)
        executor = self.executor_factory(runtime_bundle)

        try:
            initial_request = LlmRequest(
                system_prompt=runtime_bundle.prompt_view.system_prompt,
                context_prompt=runtime_bundle.prompt_view.context_prompt,
                messages=[
                    LlmMessage(role="user", content=self._build_user_message_content(input_event)),
                ],
                tools=list(runtime_bundle.tool_view.model_tools),
                tool_choice=runtime_bundle.tool_view.tool_choice,
                model=runtime_bundle.executor_config.get("model", ""),
            )
            llm_response = executor.execute(runtime_bundle, initial_request)
        except Exception as exc:
            if self._is_worker_run(runtime_bundle):
                self._persist_worker_failure(runtime_bundle, error=str(exc))
            self._emit_run_completed(runtime_bundle, status="failed")
            raise

        if self._is_worker_run(runtime_bundle):
            if runtime_bundle.tool_view.runtime_tools_enabled:
                runtime_bundle.tool_registry.dispatch(runtime_bundle, llm_response.tool_calls)
                refreshed_run = self.agent_run_repository.get_by_id(run_id)
                if refreshed_run is not None:
                    runtime_bundle.agent_run = refreshed_run
            self._persist_worker_success(runtime_bundle, llm_response)
            self._emit_agent_reply(runtime_bundle, llm_response)
            self._emit_run_completed(runtime_bundle, status=runtime_bundle.agent_run.status)
            return AgentRunInputResponse(run_id=run_id, status="accepted")

        if runtime_bundle.tool_view.runtime_tools_enabled:
            llm_response = self._run_internal_orchestrator_tool_loop(runtime_bundle, executor, initial_request, llm_response)
        self._emit_agent_reply(runtime_bundle, llm_response)
        loop_result = self.loop_engine.run(runtime_bundle, input_event)

        if loop_result.next_status is not None:
            self.agent_run_repository.update_status(run_id, loop_result.next_status)
            self._emit_run_completed(runtime_bundle, status=loop_result.next_status)

        return AgentRunInputResponse(run_id=run_id, status="accepted")

    def _persist_domain_event(self, runtime_bundle, input_event: InputEventModel) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        if input_event.type.value != "user_input":
            return

        sequence_no = self.domain_event_repository.next_sequence_no(session_id)
        self.domain_event_repository.create(
            DomainEventModel(
                event_id=uuid4(),
                session_id=session_id,
                session_workspace_id=runtime_bundle.agent_run.workspace_id,
                run_id=runtime_bundle.agent_run.run_id,
                event_type="session.message.appended",
                event_scope="main_timeline",
                sequence_no=sequence_no,
                payload={
                    "role": "user",
                    "content": self._build_user_message_content(input_event),
                },
            )
        )

    def _emit_run_started(self, runtime_bundle) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        self.domain_event_emitter.emit(
            session_id=session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="run.started",
            event_scope="main_timeline",
            payload={
                "run_id": str(runtime_bundle.agent_run.run_id),
                "role": runtime_bundle.role,
            },
        )

    def _emit_agent_reply(self, runtime_bundle, llm_response) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        content = getattr(llm_response, "content", None)
        if not isinstance(content, str) or not content.strip():
            return
        self.domain_event_emitter.emit(
            session_id=session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="session.message.appended",
            event_scope="main_timeline",
            payload={"role": "assistant", "content": content},
        )

    def _emit_run_completed(self, runtime_bundle, *, status: str) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        self.domain_event_emitter.emit(
            session_id=session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="run.completed",
            event_scope="main_timeline",
            payload={"run_id": str(runtime_bundle.agent_run.run_id), "status": status},
        )

    def _emit_tool_call(self, runtime_bundle, tool_call: dict) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
        raw_args = function.get("arguments")
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except (ValueError, TypeError):
            arguments = {"_raw": raw_args}
        self.domain_event_emitter.emit(
            session_id=session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="agent.tool_call",
            event_scope="main_timeline",
            payload={
                "tool_name": function.get("name", ""),
                "tool_call_id": tool_call.get("id", "") if isinstance(tool_call, dict) else "",
                "arguments": arguments,
            },
        )

    def _emit_tool_result(self, runtime_bundle, item: dict) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        result = item.get("result")
        # 结果可能是 pydantic 模型/对象，统一转成可 JSON 序列化的形态
        if hasattr(result, "model_dump"):
            result_payload = result.model_dump(mode="json")
        elif isinstance(result, (dict, list, str, int, float, bool)) or result is None:
            result_payload = result
        else:
            result_payload = str(result)
        self.domain_event_emitter.emit(
            session_id=session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="agent.tool_result",
            event_scope="main_timeline",
            payload={
                "tool_name": item.get("name", ""),
                "tool_call_id": item.get("tool_call_id", ""),
                "result": result_payload,
            },
        )

    def _emit_plan_updated(self, runtime_bundle) -> None:
        session_id = runtime_bundle.agent_run.session_id
        if session_id is None:
            return
        plan = self.plan_repository.get_by_run_id(runtime_bundle.agent_run.run_id)
        if plan is None:
            return
        self.domain_event_emitter.emit(
            session_id=session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="plan.updated",
            event_scope="main_timeline",
            payload={
                "plan_id": str(plan.plan_id),
                "title": plan.title,
                "goal": plan.goal,
                "status": plan.status,
                "summary": plan.summary,
                "steps": plan.steps,
                "file_path": plan.file_path,
            },
        )

    def _prepare_run_status(self, runtime_bundle, input_event: InputEventModel) -> None:
        updated_run = None
        if self._is_worker_run(runtime_bundle) and input_event.type.value == "user_input":
            updated_run = self.agent_run_repository.update_status(runtime_bundle.agent_run.run_id, "running")
        elif runtime_bundle.role == "orchestrator" and input_event.type.value == "worker_callback":
            updated_run = self.agent_run_repository.update_status(runtime_bundle.agent_run.run_id, "updating_plan")

        if updated_run is not None:
            runtime_bundle.agent_run = updated_run

    def _is_framework_worker(self, runtime_bundle) -> bool:
        return False

    def _is_worker_run(self, runtime_bundle) -> bool:
        return runtime_bundle.role == "worker"

    def _persist_framework_result(self, runtime_bundle, *, status: str, response=None, error: str | None = None) -> None:
        raise RuntimeError("framework worker path has been removed")

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

    def _run_internal_orchestrator_tool_loop(self, runtime_bundle, executor, request: LlmRequest, llm_response):
        current_request = request
        current_response = llm_response
        max_rounds = 8

        for _ in range(max_rounds):
            if not current_response.tool_calls:
                return current_response

            # 本轮工具调用前，若 LLM 先产出了一段思考/说明文字，作为独立气泡推出
            if current_response.content and current_response.content.strip():
                self._emit_agent_reply(runtime_bundle, current_response)

            # 每个工具调用单独 emit，前端时间线内联展示
            for tool_call in current_response.tool_calls:
                self._emit_tool_call(runtime_bundle, tool_call)

            tool_results = runtime_bundle.tool_registry.dispatch(runtime_bundle, current_response.tool_calls)
            refreshed_run = self.agent_run_repository.get_by_id(runtime_bundle.agent_run.run_id)
            if refreshed_run is not None:
                runtime_bundle.agent_run = refreshed_run

            # 每个工具结果 emit；plan_tool 额外 emit plan.updated 带完整步骤
            for item in tool_results:
                self._emit_tool_result(runtime_bundle, item)
                if item.get("name") == "plan_tool":
                    self._emit_plan_updated(runtime_bundle)

            messages = list(current_request.messages)
            if current_response.content:
                messages.append(LlmMessage(role="assistant", content=current_response.content))
            for item in tool_results:
                messages.append(
                    LlmMessage(
                        role="tool",
                        content=self._format_tool_result_message(item),
                    )
                )

            current_request = LlmRequest(
                system_prompt=current_request.system_prompt,
                context_prompt=current_request.context_prompt,
                messages=messages,
                tools=current_request.tools,
                tool_choice=current_request.tool_choice,
                model=current_request.model,
            )
            current_response = executor.execute(runtime_bundle, current_request)

        return current_response

    def _format_tool_result_message(self, item: dict[str, object]) -> str:
        return (
            f"tool_name={item['name']}\n"
            f"tool_call_id={item['tool_call_id']}\n"
            f"result={item['result']}"
        )
