from __future__ import annotations

import asyncio
import logging

from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage
from redis.asyncio import Redis

from app.runtime.agentscope.chat_run_registry import ChatRunRegistry
from app.runtime.agentscope.chat_runtime import AgentScopeChatRuntime

logger = logging.getLogger(__name__)


class WakeupDispatcher:
    def __init__(
        self,
        *,
        redis_url: str,
        chat_runtime: AgentScopeChatRuntime,
        chat_run_registry: ChatRunRegistry,
    ) -> None:
        self._redis_url = redis_url
        self._chat_runtime = chat_runtime
        self._registry = chat_run_registry
        self._redis: Redis | None = None
        self._message_bus: RedisMessageBus | None = None
        self._storage: RedisStorage | None = None
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> WakeupDispatcher:
        self._redis = Redis.from_url(self._redis_url, decode_responses=True, socket_timeout=None)
        self._message_bus = RedisMessageBus(connection_pool=self._redis.connection_pool)
        self._storage = RedisStorage(connection_pool=self._redis.connection_pool)
        await self._storage.__aenter__()
        await self._message_bus.__aenter__()
        ready = asyncio.Event()
        self._task = asyncio.create_task(self._loop(ready), name="agenthub-wakeup-dispatcher")
        await ready.wait()
        await self._drain_and_dispatch()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._message_bus is not None:
            await self._message_bus.__aexit__(None, None, None)
            self._message_bus = None
        if self._storage is not None:
            await self._storage.__aexit__(None, None, None)
            self._storage = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _loop(self, ready: asyncio.Event) -> None:
        try:
            if self._message_bus is None:
                raise RuntimeError("WakeupDispatcher message bus is not initialized")
            async for _signal in self._message_bus.subscribe_wakeup_signal(on_ready=ready.set):
                await self._drain_and_dispatch()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WakeupDispatcher loop crashed.")

    async def _drain_and_dispatch(self) -> None:
        if self._message_bus is None or self._storage is None:
            raise RuntimeError("WakeupDispatcher is not initialized")
        entries = await self._message_bus.dequeue_wakeups(max_count=64)
        logger.info("WakeupDispatcher: drained %d wakeup entrie(s)", len(entries))
        for payload in entries:
            try:
                user_id = payload["user_id"]
                session_id = payload["session_id"]
                agent_id = payload["agent_id"]
            except (KeyError, TypeError):
                logger.warning("WakeupDispatcher: malformed wakeup payload %r", payload)
                continue

            logger.info(
                "WakeupDispatcher: processing wakeup user_id=%s session_id=%s agent_id=%s",
                user_id,
                session_id,
                agent_id,
            )

            if await self._message_bus.session_is_running(session_id):
                logger.info(
                    "WakeupDispatcher: skipping session %s because it is already running",
                    session_id,
                )
                continue

            if await self._storage.get_session(user_id, agent_id, session_id) is None:
                logger.info(
                    "WakeupDispatcher: skipping missing session %s for agent %s",
                    session_id,
                    agent_id,
                )
                continue

            try:
                self._registry.spawn(
                    self._chat_runtime.run_wakeup(
                        user_id=user_id,
                        session_id=session_id,
                        agent_id=agent_id,
                    ),
                    session_id=session_id,
                    name=f"wakeup-run:{session_id}",
                )
                logger.info(
                    "WakeupDispatcher: spawned wakeup run for session %s agent %s",
                    session_id,
                    agent_id,
                )
            except RuntimeError:
                logger.debug(
                    "WakeupDispatcher: local run already exists for session %s",
                    session_id,
                )

    async def drain_once(self) -> None:
        redis = Redis.from_url(self._redis_url, decode_responses=True, socket_timeout=None)
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        storage = RedisStorage(connection_pool=redis.connection_pool)
        async with storage, message_bus:
            entries = await message_bus.dequeue_wakeups(max_count=64)
            logger.info(
                "WakeupDispatcher: opportunistic drain got %d wakeup entrie(s)",
                len(entries),
            )
            for payload in entries:
                try:
                    user_id = payload["user_id"]
                    session_id = payload["session_id"]
                    agent_id = payload["agent_id"]
                except (KeyError, TypeError):
                    logger.warning("WakeupDispatcher: malformed wakeup payload %r", payload)
                    continue

                if await message_bus.session_is_running(session_id):
                    logger.info(
                        "WakeupDispatcher: opportunistic drain skipping "
                        "session %s because it is already running",
                        session_id,
                    )
                    continue

                if await storage.get_session(user_id, agent_id, session_id) is None:
                    logger.info(
                        "WakeupDispatcher: opportunistic drain skipping "
                        "missing session %s for agent %s",
                        session_id,
                        agent_id,
                    )
                    continue

                await self._chat_runtime.run_wakeup(
                    user_id=user_id,
                    session_id=session_id,
                    agent_id=agent_id,
                )
        await redis.aclose()
