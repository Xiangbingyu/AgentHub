from __future__ import annotations

from agentscope.app.storage import RedisStorage
from agentscope.app.storage._model._session import ChatModelConfig, SessionConfig
from agentscope.state import AgentState
from redis.asyncio import Redis


class AgentScopeSessionStateRuntime:
    def __init__(self, storage: RedisStorage | None = None, redis: Redis | None = None) -> None:
        self._storage = storage
        self._redis = redis

    def build_session_config(
        self,
        workspace_id: str,
        name: str,
        chat_model_config: ChatModelConfig | None = None,
    ) -> SessionConfig:
        return SessionConfig(
            workspace_id=workspace_id,
            name=name,
            chat_model_config=chat_model_config,
            fallback_chat_model_config=None,
        )

    async def create_runtime_session(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
        workspace_id: str,
        name: str,
        chat_model_config: ChatModelConfig | None = None,
    ) -> None:
        if self._storage is not None:
            await self._storage.upsert_session(
                user_id=user_id,
                agent_id=agent_id,
                config=self.build_session_config(
                    workspace_id=workspace_id,
                    name=name,
                    chat_model_config=chat_model_config,
                ),
                state=AgentState(),
                session_id=session_id,
            )
            return

        if self._redis is None:
            return

        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            await storage.upsert_session(
                user_id=user_id,
                agent_id=agent_id,
                config=self.build_session_config(
                    workspace_id=workspace_id,
                    name=name,
                    chat_model_config=chat_model_config,
                ),
                state=AgentState(),
                session_id=session_id,
            )

    async def get_runtime_session(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
    ):
        if self._storage is not None:
            return await self._storage.get_session(user_id, agent_id, session_id)
        if self._redis is None:
            return None
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            return await storage.get_session(user_id, agent_id, session_id)

    async def list_runtime_messages(
        self,
        user_id: str,
        session_id: str,
        offset: int = 0,
        limit: int = 200,
    ):
        if self._storage is not None:
            return await self._storage.list_messages(
                user_id,
                session_id,
                offset=offset,
                limit=limit,
            )
        if self._redis is None:
            return []
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            return await storage.list_messages(user_id, session_id, offset=offset, limit=limit)

    async def update_runtime_state(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
        state: AgentState,
    ) -> None:
        if self._storage is not None:
            await self._storage.update_session_state(
                user_id,
                agent_id,
                session_id,
                state,
            )
            return
        if self._redis is None:
            return
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            await storage.update_session_state(user_id, agent_id, session_id, state)

    async def get_runtime_message(
        self,
        user_id: str,
        session_id: str,
        message_id: str,
    ):
        if self._storage is not None:
            return await self._storage.get_message(user_id, session_id, message_id)
        if self._redis is None:
            return None
        storage = RedisStorage(connection_pool=self._redis.connection_pool)
        async with storage:
            return await storage.get_message(user_id, session_id, message_id)
