from __future__ import annotations

from agentscope.app._manager import BackgroundTaskManager
from agentscope.app._manager._scheduler import SchedulerManager
from agentscope.app._service._chat import ChatService
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.event import HintBlockEvent, UserConfirmResultEvent
from agentscope.message import AssistantMsg, HintBlock, UserMsg
from redis.asyncio import Redis

from app.runtime.agentscope.workspace_runtime import WorkspaceRuntimeManager


class AgentScopeChatRuntime:
    def __init__(self, redis_url: str, workspace_runtime: WorkspaceRuntimeManager) -> None:
        self._redis_url = redis_url
        self._workspace_runtime = workspace_runtime

    def _new_redis(self) -> Redis:
        return Redis.from_url(self._redis_url, decode_responses=True, socket_timeout=None)

    def build_chat_service(
        self,
        *,
        storage: RedisStorage,
        message_bus: RedisMessageBus,
        scheduler_manager: SchedulerManager,
        background_task_manager: BackgroundTaskManager,
    ) -> ChatService:
        return ChatService(
            storage=storage,
            workspace_manager=self._workspace_runtime,
            scheduler_manager=scheduler_manager,
            background_task_manager=background_task_manager,
            message_bus=message_bus,
        )

    async def _persist_wakeup_hints(
        self,
        *,
        storage: RedisStorage,
        message_bus: RedisMessageBus,
        user_id: str,
        session_id: str,
        agent_id: str,
    ) -> None:
        entries = await message_bus.inbox_drain(session_id, max_count=100)
        if not entries:
            return

        hint_blocks = [HintBlock.model_validate(payload) for _entry_id, payload in entries]
        if not hint_blocks:
            return

        agent_record = await storage.get_agent(user_id, agent_id)
        agent_name = agent_id if agent_record is None else agent_record.data.name
        hint_message = AssistantMsg(name=agent_name, content=list(hint_blocks))
        await storage.upsert_message(user_id, session_id, hint_message)

        runtime_session = await storage.get_session(user_id, agent_id, session_id)
        if runtime_session is not None:
            runtime_session.state.context.append(hint_message)
            await storage.update_session_state(
                user_id=user_id,
                agent_id=agent_id,
                session_id=session_id,
                state=runtime_session.state,
            )

        for hint in hint_blocks:
            await message_bus.session_publish_event(
                session_id,
                HintBlockEvent(
                    reply_id=hint_message.id,
                    block_id=hint.id,
                    source=hint.source,
                    hint=hint.hint,
                ).model_dump(mode="json"),
            )

    async def run_user_message(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
        content: str,
    ) -> None:
        redis = self._new_redis()
        storage = RedisStorage(connection_pool=redis.connection_pool)
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with storage, message_bus, self._workspace_runtime as workspace_manager:
            background_task_manager = BackgroundTaskManager()
            scheduler_manager = SchedulerManager(storage=storage, message_bus=message_bus)
            async with scheduler_manager:
                chat_service = ChatService(
                    storage=storage,
                    workspace_manager=workspace_manager,
                    scheduler_manager=scheduler_manager,
                    background_task_manager=background_task_manager,
                    message_bus=message_bus,
                )
                await chat_service.run(
                    user_id=user_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    input_msg=UserMsg(name="user", content=content),
                )
        await redis.aclose()

    async def run_wakeup(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
    ) -> None:
        redis = self._new_redis()
        storage = RedisStorage(connection_pool=redis.connection_pool)
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with storage, message_bus, self._workspace_runtime as workspace_manager:
            await self._persist_wakeup_hints(
                storage=storage,
                message_bus=message_bus,
                user_id=user_id,
                session_id=session_id,
                agent_id=agent_id,
            )
            background_task_manager = BackgroundTaskManager()
            scheduler_manager = SchedulerManager(storage=storage, message_bus=message_bus)
            async with scheduler_manager:
                chat_service = ChatService(
                    storage=storage,
                    workspace_manager=workspace_manager,
                    scheduler_manager=scheduler_manager,
                    background_task_manager=background_task_manager,
                    message_bus=message_bus,
                )
                await chat_service.run(
                    user_id=user_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    input_msg=None,
                )
        await redis.aclose()

    async def continue_with_confirm_event(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
        event: UserConfirmResultEvent,
    ) -> None:
        redis = self._new_redis()
        storage = RedisStorage(connection_pool=redis.connection_pool)
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with storage, message_bus, self._workspace_runtime as workspace_manager:
            background_task_manager = BackgroundTaskManager()
            scheduler_manager = SchedulerManager(storage=storage, message_bus=message_bus)
            async with scheduler_manager:
                chat_service = ChatService(
                    storage=storage,
                    workspace_manager=workspace_manager,
                    scheduler_manager=scheduler_manager,
                    background_task_manager=background_task_manager,
                    message_bus=message_bus,
                )
                await chat_service.run(
                    user_id=user_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    input_msg=event,
                )
        await redis.aclose()

    async def publish_cancel(self, session_id: str) -> None:
        redis = self._new_redis()
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with message_bus:
            await message_bus.session_publish_cancel(session_id)
        await redis.aclose()
