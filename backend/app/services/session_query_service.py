from __future__ import annotations

from agentscope.app.message_bus import RedisMessageBus

from app.domain.sessions.models import AgentStatus, WaitingItem
from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.storage.session_repository import SessionRepository
from app.infrastructure.storage.team_repository import TeamRepository
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime
from app.runtime.agentscope.team_runtime import AgentScopeTeamRuntime
from app.services.workspace_query_service import WorkspaceQueryService


class SessionQueryService:
    def __init__(
        self,
        session_repository: SessionRepository,
        team_repository: TeamRepository,
        workspace_repository: WorkspaceRepository,
        state_runtime: AgentScopeSessionStateRuntime,
        workspace_query_service: WorkspaceQueryService,
        team_runtime: AgentScopeTeamRuntime,
        runtime_principal: str,
    ) -> None:
        self._session_repository = session_repository
        self._team_repository = team_repository
        self._workspace_repository = workspace_repository
        self._state_runtime = state_runtime
        self._workspace_query_service = workspace_query_service
        self._team_runtime = team_runtime
        self._runtime_principal = runtime_principal

    async def list_sessions(self) -> dict:
        sessions = await self._session_repository.list_all()
        return {"sessions": [session.model_dump(mode="json") for session in sessions]}

    async def get_session_detail(self, session_id: str) -> dict:
        session = await self._session_repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        team = await self._team_repository.get_team(session.team_id)
        workspace = await self._workspace_repository.get(session.workspace_id)
        runtime_session = await self._state_runtime.get_runtime_session(
            user_id=self._runtime_principal,
            session_id=session.session_id,
            agent_id=session.leader_agent_id,
        )
        messages = await self._state_runtime.list_runtime_messages(
            user_id=self._runtime_principal,
            session_id=session.session_id,
        )
        messages = self._merge_context_messages(messages, runtime_session)
        messages = await self._merge_hint_event_messages(messages, session.session_id)
        agent_statuses = [] if team is None else self._build_agent_statuses(session, team)
        waiting_items = [] if team is None else await self._build_waiting_items(session, team)
        plan_snapshot = await self._workspace_query_service.read_plan_snapshot(
            session.workspace_id
        )
        return {
            "session": session.model_dump(mode="json"),
            "team": None if team is None else team.model_dump(mode="json"),
            "messages": [message.model_dump(mode="json") for message in messages],
            "runtime": {
                "current_plan": (
                    plan_snapshot
                    if plan_snapshot is not None
                    else session.current_plan_snapshot
                ),
                "current_summary": session.current_summary_snapshot,
                "waiting_items": [item.model_dump(mode="json") for item in waiting_items],
                "agent_statuses": [item.model_dump(mode="json") for item in agent_statuses],
            },
            "workspace_status": {
                "workspace_id": session.workspace_id,
                "name": None if workspace is None else workspace.name,
                "root_path": None if workspace is None else workspace.root_path,
                "status": None if workspace is None else workspace.status,
            },
        }

    @staticmethod
    def _build_agent_statuses(session, team) -> list[AgentStatus]:
        existing_by_id = {item.agent_id: item for item in session.agent_statuses}
        agent_statuses: list[AgentStatus] = []
        leader_runtime_status = (
            "waiting"
            if session.waiting_items
            else "cancelled"
            if session.status == "cancelling"
            else session.status
        )

        leader_status = existing_by_id.get(team.leader_agent_id)
        agent_statuses.append(
            leader_status
            if leader_status is not None
            else AgentStatus(
                runtime_id=team.leader_agent_id,
                agent_id=team.leader_agent_id,
                name=team.leader_agent_id,
                role="leader",
                kind="leader",
                status=leader_runtime_status,
            )
        )

        for worker_agent_id in team.member_agent_ids:
            worker_status = existing_by_id.get(worker_agent_id)
            agent_statuses.append(
                worker_status
                if worker_status is not None
                else AgentStatus(
                    runtime_id=worker_agent_id,
                    agent_id=worker_agent_id,
                    name=worker_agent_id,
                    role="worker",
                    kind="worker",
                    status="idle",
                )
            )

        return agent_statuses

    async def _build_waiting_items(self, session, team) -> list[WaitingItem]:
        waiting_items = list(session.waiting_items)
        seen_ids = {item.waiting_id for item in waiting_items}

        for worker_agent_id in team.member_agent_ids:
            runtime_session = await self._state_runtime.get_runtime_session(
                user_id=self._runtime_principal,
                session_id=self._team_runtime.build_worker_session_id(
                    session.session_id,
                    worker_agent_id,
                ),
                agent_id=worker_agent_id,
            )
            if runtime_session is None:
                continue
            for item in self._extract_waiting_items_from_runtime_session(
                runtime_session,
                source_runtime_id=worker_agent_id,
                source_type="subagent",
            ):
                if item.waiting_id in seen_ids:
                    continue
                waiting_items.append(item)
                seen_ids.add(item.waiting_id)

        return waiting_items

    @staticmethod
    def _extract_waiting_items_from_runtime_session(
        runtime_session,
        *,
        source_runtime_id: str,
        source_type: str,
    ) -> list[WaitingItem]:
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
                        source_type=source_type,
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
                        source_type=source_type,
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

    @staticmethod
    def _merge_context_messages(messages: list, runtime_session) -> list:
        if runtime_session is None:
            return messages

        merged_by_id: dict[object, object] = {
            getattr(message, "id", None): message for message in messages
        }
        ordered_ids = [getattr(message, "id", None) for message in messages]
        for message in runtime_session.state.context:
            message_id = getattr(message, "id", None)
            if not hasattr(message, "role") or not hasattr(message, "content"):
                continue
            if message_id not in merged_by_id:
                ordered_ids.append(message_id)
            merged_by_id[message_id] = message
        return [merged_by_id[message_id] for message_id in ordered_ids]

    @staticmethod
    async def _merge_hint_event_messages(messages: list, session_id: str) -> list:
        has_hint = any(
            getattr(message, "role", None) == "assistant"
            and any(
                isinstance(block, dict) and block.get("type") == "hint"
                for block in message.model_dump(mode="json").get("content", [])
            )
            for message in messages
            if hasattr(message, "model_dump")
        )
        if has_hint:
            return messages

        redis = get_redis_client()
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with message_bus:
            events = await message_bus.session_read_events(session_id)

        hint_messages = []
        for _entry_id, event in events:
            if event.get("type") != "hint_block":
                continue
            hint_messages.append(
                {
                    "id": event.get("reply_id") or event.get("block_id"),
                    "role": "assistant",
                    "name": "leader-agent",
                    "content": [
                        {
                            "type": "hint",
                            "id": event.get("block_id"),
                            "source": event.get("source"),
                            "hint": event.get("hint"),
                        }
                    ],
                }
            )

        if not hint_messages:
            return messages

        return messages + hint_messages
