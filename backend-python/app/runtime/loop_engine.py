from __future__ import annotations

from app.models.input_event import InputEventModel, InputEventType
from app.repositories.agent_run_repository import AgentRunRepository
from app.runtime.loop_base import LoopAction, LoopResult
from app.runtime.runtime_assembler import RuntimeBundle


class LoopEngine:
    def __init__(self, agent_run_repository: AgentRunRepository) -> None:
        self.agent_run_repository = agent_run_repository

    def run(self, runtime: RuntimeBundle, input_event: InputEventModel) -> LoopResult:
        while True:
            loop_result = self._step(runtime, input_event)

            if loop_result.action is LoopAction.continue_:
                runtime.agent_run = runtime.agent_run.model_copy(
                    update={"status": loop_result.next_status or runtime.agent_run.status}
                )
                continue

            return loop_result

    def _step(self, runtime: RuntimeBundle, input_event: InputEventModel) -> LoopResult:
        if input_event.type == InputEventType.user_input:
            if runtime.role == "orchestrator" and runtime.agent_run.status == "created":
                next_status = "chatting"
                self.agent_run_repository.update_status(runtime.agent_run.run_id, next_status)
                return LoopResult(action=LoopAction.continue_, next_status=next_status, reason="enter chatting phase")

            next_status = runtime.agent_run.status
            self.agent_run_repository.update_status(runtime.agent_run.run_id, next_status)
            return LoopResult(action=LoopAction.wait, next_status=next_status, reason="awaiting next event")

        if input_event.type == InputEventType.worker_callback:
            next_status = runtime.agent_run.status
            if runtime.role == "orchestrator" and runtime.agent_run.status == "updating_plan":
                callback_status = str(input_event.payload.get("status") or "").strip().lower()
                next_status = "completed" if callback_status == "completed" else "failed"
                self.agent_run_repository.update_status(runtime.agent_run.run_id, next_status)
            return LoopResult(action=LoopAction.wait, next_status=next_status, reason="worker callback received")

        return LoopResult(action=LoopAction.stop, next_status=runtime.agent_run.status, reason="unsupported input type")
