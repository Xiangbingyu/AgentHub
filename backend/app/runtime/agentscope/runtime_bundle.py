from __future__ import annotations

from app.runtime.agentscope.chat_runtime import AgentScopeChatRuntime
from app.runtime.agentscope.wakeup_dispatcher import WakeupDispatcher
from app.runtime.agentscope.workspace_runtime import WorkspaceRuntimeManager


class AgentScopeRuntimeBundle:
    def __init__(self, redis_url: str, workspace_base_dir: str, chat_run_registry) -> None:
        self._redis_url = redis_url
        self._workspace_runtime = WorkspaceRuntimeManager(workspace_base_dir)
        self._chat_runtime = AgentScopeChatRuntime(
            redis_url=redis_url,
            workspace_runtime=self._workspace_runtime,
        )
        self._wakeup_dispatcher = WakeupDispatcher(
            redis_url=redis_url,
            chat_runtime=self._chat_runtime,
            chat_run_registry=chat_run_registry,
        )

    @property
    def chat_runtime(self) -> AgentScopeChatRuntime:
        return self._chat_runtime

    @property
    def wakeup_dispatcher(self) -> WakeupDispatcher:
        return self._wakeup_dispatcher

    async def drain_wakeups_once(self) -> None:
        await self._wakeup_dispatcher.drain_once()

    async def __aenter__(self) -> AgentScopeRuntimeBundle:
        await self._wakeup_dispatcher.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._wakeup_dispatcher.__aexit__(*exc)
