from __future__ import annotations

import json
import threading
import time
from uuid import UUID, uuid4

from agent_service.app.config import get_settings
from agent_service.app.llm.llm_executor import InternalLlmExecutor
from agent_service.app.llm.llm_types import LlmMessage, LlmRequest, LlmResponse
from agent_service.app.models.domain_event import DomainEventModel
from agent_service.app.models.input_event import InputEventModel
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.runtime.loop_engine import LoopEngine
from agent_service.app.runtime.prompt.prompt_composer import PromptComposer
from agent_service.app.runtime.runtime_assembler import RuntimeAssembler
from agent_service.app.schemas.agent_run_input import AgentRunInputRequest, AgentRunInputResponse
from agent_service.app.services.domain_event_emitter import DomainEventEmitter
from agent_service.app.services.turn_coordinator import TURN_COORDINATOR


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
        settings = get_settings()
        self.turn_deadline_seconds = settings.turn_deadline_seconds
        self.history_max_messages = settings.history_max_messages
        self.turn_coordinator = TURN_COORDINATOR

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

        # 注册本回合：若该 run 已有进行中的回合，会给它置中断标志，让其在下一轮边界停下。
        turn = self.turn_coordinator.begin(run_id)
        try:
            return self._run_turn(run_id, input_event, turn)
        finally:
            self.turn_coordinator.end(run_id, turn.token)

    def _run_turn(self, run_id, input_event, turn) -> AgentRunInputResponse:
        runtime_bundle = self.runtime_assembler.build(run_id)
        # 把本回合的中断标志挂到 bundle 上，使工具执行层（bash_tool 等）能抢占式停止。
        runtime_bundle.cancel_event = turn.cancel_event
        self._persist_domain_event(runtime_bundle, input_event)
        self._prepare_run_status(runtime_bundle, input_event)
        self._emit_run_started(runtime_bundle)
        runtime_bundle.prompt_view = self.prompt_composer.compose(runtime_bundle, input_event)
        executor = self.executor_factory(runtime_bundle)

        try:
            initial_request = LlmRequest(
                system_prompt=runtime_bundle.prompt_view.system_prompt,
                context_prompt=runtime_bundle.prompt_view.context_prompt,
                messages=self._build_conversation_messages(runtime_bundle, input_event),
                tools=list(runtime_bundle.tool_view.model_tools),
                tool_choice=runtime_bundle.tool_view.tool_choice,
                model=runtime_bundle.executor_config.get("model", ""),
            )
            llm_response = self._execute_with_interrupt(executor, runtime_bundle, initial_request, turn)
        except Exception as exc:
            if self._is_worker_run(runtime_bundle):
                self._persist_worker_failure(runtime_bundle, error=str(exc))
                self._emit_run_completed(runtime_bundle, status="failed")
                raise
            # 编排者首次 LLM 调用失败：给可见收尾 + 结束回合，会话保持可继续，不静默 500。
            terminal = self._terminal_error_response(LlmResponse(content="", tool_calls=[], raw={}), exc)
            self._emit_agent_reply(runtime_bundle, terminal)
            self.agent_run_repository.update_status(run_id, "chatting")
            self._emit_run_completed(runtime_bundle, status="chatting")
            return AgentRunInputResponse(run_id=run_id, status="accepted")

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
            llm_response = self._run_internal_orchestrator_tool_loop(
                runtime_bundle, executor, initial_request, llm_response, turn
            )
        # 被新消息中断：显式发 interrupted 收尾，避免前端永远等待 loading。
        if turn.cancel_event.is_set():
            self._emit_run_completed(runtime_bundle, status="interrupted")
            return AgentRunInputResponse(run_id=run_id, status="accepted")

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

        self.domain_event_repository.append(
            DomainEventModel(
                event_id=uuid4(),
                session_id=session_id,
                session_workspace_id=runtime_bundle.agent_run.workspace_id,
                run_id=runtime_bundle.agent_run.run_id,
                event_type="session.message.appended",
                event_scope="main_timeline",
                sequence_no=0,
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

    def _build_conversation_messages(
        self, runtime_bundle, input_event: InputEventModel
    ) -> list[LlmMessage]:
        """重建本 run 的多轮对话，给 LLM 提供上下文连续性。

        历史来源是已持久化的 session.message.appended 事件（user/assistant），
        当前这轮的用户消息在 input() 中已先行落事件，因此天然包含在末尾。
        无 session（如部分 worker/测试场景）时回退为仅当前消息。
        """
        session_id = runtime_bundle.agent_run.session_id
        fallback = [LlmMessage(role="user", content=self._build_user_message_content(input_event))]
        if session_id is None:
            return fallback

        events = self.domain_event_repository.list_by_run_id(runtime_bundle.agent_run.run_id)
        messages: list[LlmMessage] = []
        for event in events:
            if event.event_type != "session.message.appended":
                continue
            role = event.payload.get("role")
            content = event.payload.get("content")
            if role not in ("user", "assistant"):
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            messages.append(LlmMessage(role=role, content=content))

        if not messages:
            return fallback

        if self.history_max_messages and len(messages) > self.history_max_messages:
            messages = messages[-self.history_max_messages :]
        return messages

    def _run_internal_orchestrator_tool_loop(
        self, runtime_bundle, executor, request: LlmRequest, llm_response, turn=None
    ):
        current_request = request
        current_response = llm_response
        max_rounds = 8
        deadline = None
        if self.turn_deadline_seconds:
            deadline = time.monotonic() + self.turn_deadline_seconds

        for _ in range(max_rounds):
            if not current_response.tool_calls:
                return current_response

            # 被后到的新消息中断：立即停下，把控制权交给接管的新回合。
            if turn is not None and turn.cancel_event.is_set():
                return current_response

            # 超过本轮 run 的墙钟时限则强制收尾，避免无限运行 / 静默不结束。
            if deadline is not None and time.monotonic() >= deadline:
                return self._terminal_timeout_response(current_response)

            # 本轮工具调用前，若 LLM 先产出了一段思考/说明文字，作为独立气泡推出
            if current_response.content and current_response.content.strip():
                self._emit_agent_reply(runtime_bundle, current_response)

            # 每个工具调用单独 emit，前端时间线内联展示
            for tool_call in current_response.tool_calls:
                self._emit_tool_call(runtime_bundle, tool_call)

            try:
                tool_results = runtime_bundle.tool_registry.dispatch(
                    runtime_bundle, current_response.tool_calls
                )
            except Exception as exc:  # 工具执行抛错也要收尾，不能让本轮静默死掉
                return self._terminal_error_response(current_response, exc)
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
                messages.append(
                    LlmMessage(
                        role="assistant",
                        content=current_response.content,
                        tool_calls=list(current_response.tool_calls),
                    )
                )
            for item in tool_results:
                messages.append(
                    LlmMessage(
                        role="tool",
                        content=self._format_tool_result_message(item),
                        tool_call_id=str(item["tool_call_id"] or ""),
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
            try:
                current_response = self._execute_with_interrupt(executor, runtime_bundle, current_request, turn)
            except Exception as exc:  # 轮间 LLM 调用抛错（超时/5xx/响应异常）是静默卡死的主因
                return self._terminal_error_response(current_response, exc)

        # 跑满轮次仍带未处理的工具调用：给出明确收尾，不静默结束。
        if current_response.tool_calls:
            return self._terminal_notice_response(
                current_response,
                f"本轮已达到工具调用上限（{max_rounds} 轮）并自动结束，可能未完成全部步骤。",
            )
        return current_response

    def _terminal_timeout_response(self, last_response):
        return self._terminal_notice_response(
            last_response,
            f"本轮已达到时限（{int(self.turn_deadline_seconds)} 秒）并自动结束，可能未完成全部步骤。",
        )

    def _terminal_notice_response(self, last_response, reason: str):
        """把强制收尾原因并入最后一段回复，确保 run 始终有可见的结束回复。"""
        content = (last_response.content or "").strip()
        notice = f"{reason}请查看工作区当前状态后再继续。"
        merged = f"{content}\n\n{notice}" if content else notice
        raw = getattr(last_response, "raw", {}) or {}
        return LlmResponse(content=merged, tool_calls=[], raw=raw)

    def _terminal_error_response(self, last_response, exc: Exception):
        """工具/LLM 调用抛错时的收尾：把错误并入回复，避免本轮静默卡死。"""
        reason = f"本轮执行出错并自动结束：{type(exc).__name__}: {exc}。"
        return self._terminal_notice_response(last_response, reason)

    def _execute_with_interrupt(self, executor, runtime_bundle, request, turn):
        if turn is None:
            return executor.execute(runtime_bundle, request)

        result: dict[str, object] = {}
        error: dict[str, Exception] = {}

        def _run() -> None:
            try:
                result["response"] = executor.execute(runtime_bundle, request)
            except Exception as exc:  # pragma: no cover - surfaced to caller below
                error["exc"] = exc

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        while worker.is_alive():
            if turn.cancel_event.is_set():
                return LlmResponse(content="", tool_calls=[], raw={"interrupted": True})
            worker.join(0.1)

        if "exc" in error:
            raise error["exc"]
        return result["response"]

    def _format_tool_result_message(self, item: dict[str, object]) -> str:
        return (
            f"tool_name={item['name']}\n"
            f"tool_call_id={item['tool_call_id']}\n"
            f"result={item['result']}"
        )
