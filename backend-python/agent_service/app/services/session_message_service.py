from __future__ import annotations

import threading
from uuid import UUID, uuid4

from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.schemas.agent_run_create import AgentRunCreateRequest
from agent_service.app.schemas.agent_run_input import AgentRunInputRequest, AgentRunInputResponse
from agent_service.app.services.agent_run_create_service import AgentRunCreateService
from agent_service.app.services.turn_coordinator import TURN_COORDINATOR


class SessionMessageService:
    """前端只持有 session_id 的发消息入口。

    内部解析该 session 的活动 orchestrator run（没有则新建一个），再转发到
    ``AgentRunInputService.input``。``input_service`` 可注入以便测试不打真实 LLM。

    LLM 执行经 ``async_runner`` 在后台线程跑（默认 daemon 线程），``send`` 录入
    用户消息后立即返回，agent 回复经 SSE 回流——避免同步阻塞触发 gateway 超时。
    测试可注入同步 ``async_runner`` 以拿到确定性结果。
    """

    def __init__(
        self,
        input_service=None,
        session_repository: SessionRepository | None = None,
        agent_run_repository: AgentRunRepository | None = None,
        agent_repository: AgentRepository | None = None,
        async_runner=None,
    ) -> None:
        self.session_repository = session_repository or SessionRepository()
        self.agent_run_repository = agent_run_repository or AgentRunRepository()
        self.agent_repository = agent_repository or AgentRepository()
        self._input_service = input_service
        self._async_runner = async_runner or self._run_async
        self.turn_coordinator = TURN_COORDINATOR
        self._create_service = AgentRunCreateService(
            agent_repository=self.agent_repository,
            agent_run_repository=self.agent_run_repository,
        )

    def _run_async(self, job) -> None:
        thread = threading.Thread(target=job, daemon=True)
        thread.start()

    def _resolve_input_service(self):
        if self._input_service is not None:
            return self._input_service
        # 延迟构造：InternalLlmExecutor 需要 env，避免在 import / 无需执行时触发
        from agent_service.app.services.agent_run_input_service import AgentRunInputService

        return AgentRunInputService(
            agent_run_repository=self.agent_run_repository,
            agent_repository=self.agent_repository,
            input_event_repository=InputEventRepository(),
        )

    def _resolve_run_id(self, session) -> UUID:
        existing = self.agent_run_repository.list_by_session_id(session.session_id)
        orchestrator_runs = [run for run in existing if run.agent_kind == "orchestrator"]
        if orchestrator_runs:
            latest_run = max(orchestrator_runs, key=lambda run: run.updated_at)
            is_active = getattr(self.turn_coordinator, "is_active", lambda _run_id: False)
            if is_active(latest_run.run_id):
                self.turn_coordinator.cancel(latest_run.run_id)
                return self._create_run_for_session(session)
            return latest_run.run_id

        return self._create_run_for_session(session)

    def _create_run_for_session(self, session) -> UUID:
        orchestrators = [
            agent
            for agent in self.agent_repository.list_all()
            if agent.agent_kind == "orchestrator"
        ]
        if not orchestrators:
            raise ValueError("no orchestrator agent available")

        created = self._create_service.create_run(
            AgentRunCreateRequest(
                agent_id=orchestrators[0].agent_id,
                session_id=session.session_id,
                workspace_id=session.session_workspace_id,
                metadata={},
            )
        )
        return created.run_id

    def send(self, session_id: UUID, content: str) -> AgentRunInputResponse:
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            raise ValueError("session not found")

        run_id = self._resolve_run_id(session)
        self.turn_coordinator.cancel(run_id)
        payload = AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": content},
            idempotency_key=str(uuid4()),
        )

        # LLM 工具循环可能跑很久（多轮），放后台线程，POST 立即返回。
        # 用户消息事件在 input() 内部、LLM 调用之前落库，SSE 仍能即时推出。
        input_service = self._resolve_input_service()
        self._async_runner(lambda: input_service.input(run_id, payload))
        return AgentRunInputResponse(run_id=run_id, status="accepted")
