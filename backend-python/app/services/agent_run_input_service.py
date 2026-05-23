from __future__ import annotations

from uuid import UUID

from app.models.input_event import InputEventModel
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.agent_repository import AgentRepository
from app.repositories.input_event_repository import InputEventRepository
from app.repositories.plan_repository import PlanRepository
from app.llm.llm_executor import LlmExecutor
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
        self.llm_executor = LlmExecutor()
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
        llm_response = self.llm_executor.complete(
            LlmRequest(
                system_prompt=prompt_bundle.system_prompt,
                context_prompt=prompt_bundle.context_prompt,
                messages=[
                    LlmMessage(role="user", content=str(input_event.payload)),
                ],
                tools=runtime_bundle.get_llm_tools(),
                tool_choice=runtime_bundle.get_llm_tool_choice(),
                model="",
            )
        )
        runtime_bundle.dispatch_tool_calls(llm_response.tool_calls)
        loop_result = self.loop_engine.run(runtime_bundle, input_event)

        if loop_result.next_status is not None:
            self.agent_run_repository.update_status(run_id, loop_result.next_status)

        return AgentRunInputResponse(run_id=run_id, status="accepted")
