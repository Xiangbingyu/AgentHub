from __future__ import annotations

from collections.abc import Callable

from app.domain.sessions.models import WaitingItem
from app.infrastructure.storage.session_repository import SessionRepository
from app.runtime.agentscope.chat_runtime import AgentScopeChatRuntime
from app.runtime.agentscope.confirm_runtime import ConfirmRuntime
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime


class RuntimeService:
    def __init__(
        self,
        session_repository: SessionRepository,
        chat_runtime: AgentScopeChatRuntime | None = None,
        state_runtime: AgentScopeSessionStateRuntime | None = None,
        confirm_runtime: ConfirmRuntime | None = None,
        chat_run_registry=None,
        session_repository_factory: Callable[[], SessionRepository] | None = None,
        chat_runtime_factory: Callable[[], AgentScopeChatRuntime] | None = None,
        state_runtime_factory: Callable[[], AgentScopeSessionStateRuntime] | None = None,
        runtime_principal: str = "local-user",
    ) -> None:
        self._session_repository = session_repository
        self._chat_runtime = chat_runtime
        self._state_runtime = state_runtime
        self._confirm_runtime = confirm_runtime
        self._chat_run_registry = chat_run_registry
        self._session_repository_factory = session_repository_factory
        self._chat_runtime_factory = chat_runtime_factory
        self._state_runtime_factory = state_runtime_factory
        self._runtime_principal = runtime_principal

    async def send_message(self, session_id: str, content: str) -> None:
        session = await self._session_repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.status not in {"idle", "failed"}:
            raise ValueError("Session is not ready for a new message")
        session.status = "running"
        await self._session_repository.upsert(session)
        if self._chat_runtime is not None and self._chat_run_registry is not None:
            async def _run_and_sync() -> None:
                repository = self._build_session_repository()
                chat_runtime = self._build_chat_runtime()
                run_failed = False
                try:
                    await chat_runtime.run_user_message(
                        user_id=self._runtime_principal,
                        session_id=session.session_id,
                        agent_id=session.leader_agent_id,
                        content=content,
                    )
                except Exception:
                    run_failed = True
                    raise
                finally:
                    await self._sync_runtime_state(
                        session_repository=repository,
                        session_id=session.session_id,
                        agent_id=session.leader_agent_id,
                        failed=run_failed,
                    )

            self._chat_run_registry.spawn(
                _run_and_sync(),
                session_id=session.session_id,
            )

    async def cancel(self, session_id: str) -> None:
        session = await self._session_repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        session.status = "cancelling"
        await self._session_repository.upsert(session)
        if self._chat_run_registry is not None:
            task = self._chat_run_registry.get(session_id)
            if task is not None and not task.done():
                task.cancel()
        if self._chat_runtime is not None:
            await self._chat_runtime.publish_cancel(session_id)

    async def submit_waiting_item(
        self,
        session_id: str,
        waiting_id: str,
        confirmed: bool,
    ) -> None:
        session = await self._session_repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        target_item = None
        for item in session.waiting_items:
            if item.waiting_id == waiting_id:
                target_item = item
                item.status = "resolved" if confirmed else "rejected"
                break
        if target_item is None:
            raise KeyError(waiting_id)

        session.status = "running"

        if (
            self._state_runtime is not None
            and self._chat_runtime is not None
            and self._confirm_runtime is not None
        ):
            runtime_session = await self._state_runtime.get_runtime_session(
                user_id=self._runtime_principal,
                session_id=session.session_id,
                agent_id=session.leader_agent_id,
            )
            if runtime_session is not None and runtime_session.state.context:
                last_message = runtime_session.state.context[-1]
                reply_id = last_message.id
                for tool_call in last_message.get_content_blocks("tool_call"):
                    if tool_call.id == waiting_id:
                        event = self._confirm_runtime.build_confirm_event(
                            reply_id=reply_id,
                            confirmed=confirmed,
                            tool_call=tool_call,
                        )
                        await self._chat_runtime.continue_with_confirm_event(
                            user_id=self._runtime_principal,
                            session_id=session.session_id,
                            agent_id=session.leader_agent_id,
                            event=event,
                        )
                        break
            runtime_session = await self._state_runtime.get_runtime_session(
                user_id=self._runtime_principal,
                session_id=session.session_id,
                agent_id=session.leader_agent_id,
            )
            if runtime_session is not None:
                session.current_summary_snapshot = runtime_session.state.summary
                extracted_waiting_items = self._extract_waiting_items(
                    runtime_session,
                    source_runtime_id=session.leader_agent_id,
                )
                session.waiting_items = self._merge_waiting_items(
                    session.waiting_items,
                    extracted_waiting_items,
                )
                if session.waiting_items:
                    session.status = "waiting"
                else:
                    session.status = "idle"
        await self._session_repository.upsert(session)

    def _build_session_repository(self) -> SessionRepository:
        if self._session_repository_factory is not None:
            return self._session_repository_factory()
        return self._session_repository

    def _build_chat_runtime(self) -> AgentScopeChatRuntime:
        if self._chat_runtime_factory is not None:
            return self._chat_runtime_factory()
        if self._chat_runtime is None:
            raise RuntimeError("Chat runtime is not configured")
        return self._chat_runtime

    def _build_state_runtime(self) -> AgentScopeSessionStateRuntime | None:
        if self._state_runtime_factory is not None:
            return self._state_runtime_factory()
        return self._state_runtime

    async def _sync_runtime_state(
        self,
        session_repository: SessionRepository,
        session_id: str,
        agent_id: str,
        failed: bool,
    ) -> None:
        latest = await session_repository.get(session_id)
        if latest is None:
            return
        state_runtime = self._build_state_runtime()
        if state_runtime is not None:
            runtime_session = await state_runtime.get_runtime_session(
                user_id=self._runtime_principal,
                session_id=session_id,
                agent_id=agent_id,
            )
            if runtime_session is not None:
                latest.current_summary_snapshot = runtime_session.state.summary
                extracted_waiting_items = self._extract_waiting_items(
                    runtime_session,
                    source_runtime_id=agent_id,
                )
                latest.waiting_items = self._merge_waiting_items(
                    latest.waiting_items,
                    extracted_waiting_items,
                )
        if latest.waiting_items:
            latest.status = "waiting"
        elif latest.status == "cancelling":
            latest.status = "idle"
        elif failed:
            latest.status = "failed"
        else:
            latest.status = "idle"
        await session_repository.upsert(latest)

    @staticmethod
    def _merge_waiting_items(
        existing_items: list[WaitingItem],
        extracted_items: list[WaitingItem],
    ) -> list[WaitingItem]:
        preserved_statuses = {
            item.waiting_id: item.status
            for item in existing_items
            if item.status in {"resolved", "rejected"}
        }
        for item in extracted_items:
            preserved = preserved_statuses.get(item.waiting_id)
            if preserved is not None:
                item.status = preserved
        return extracted_items

    @staticmethod
    def _extract_waiting_items(runtime_session, source_runtime_id: str) -> list[WaitingItem]:
        context = runtime_session.state.context
        if not context:
            return []
        waiting_by_id: dict[str, WaitingItem] = {}
        for message in context:
            if not hasattr(message, "get_content_blocks"):
                continue
            for tool_call in message.get_content_blocks("tool_call"):
                if tool_call.state == "asking":
                    waiting_by_id[tool_call.id] = WaitingItem(
                        waiting_id=tool_call.id,
                        source_type="leader",
                        source_runtime_id=source_runtime_id,
                        waiting_kind="confirm",
                        title=f"Confirm tool call: {tool_call.name}",
                        message=f"Tool {tool_call.name} requires confirmation.",
                        payload={
                            "tool_name": tool_call.name,
                            "tool_input": tool_call.input,
                        },
                    )
                elif tool_call.state == "submitted":
                    waiting_by_id[tool_call.id] = WaitingItem(
                        waiting_id=tool_call.id,
                        source_type="leader",
                        source_runtime_id=source_runtime_id,
                        waiting_kind="external_result",
                        title=f"Await external result: {tool_call.name}",
                        message=f"Tool {tool_call.name} is waiting for external execution result.",
                        payload={
                            "tool_name": tool_call.name,
                            "tool_input": tool_call.input,
                        },
                    )
        return list(waiting_by_id.values())
