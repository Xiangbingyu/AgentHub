from __future__ import annotations

from app.config import Settings
from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.storage.session_repository import SessionRepository
from app.infrastructure.storage.team_repository import TeamRepository
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.infrastructure.workspace.file_browser import WorkspaceFileBrowser
from app.infrastructure.workspace.manager import WorkspacePathManager
from app.runtime.agentscope.chat_run_registry import ChatRunRegistry
from app.runtime.agentscope.chat_runtime import AgentScopeChatRuntime
from app.runtime.agentscope.confirm_runtime import ConfirmRuntime
from app.runtime.agentscope.runtime_bundle import AgentScopeRuntimeBundle
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime
from app.runtime.agentscope.team_runtime import AgentScopeTeamRuntime
from app.services.runtime_bootstrap_service import RuntimeBootstrapService
from app.services.runtime_service import RuntimeService
from app.services.session_query_service import SessionQueryService
from app.services.session_service import SessionService
from app.services.team_query_service import TeamQueryService
from app.services.team_service import TeamService
from app.services.workspace_query_service import WorkspaceQueryService
from app.services.workspace_service import WorkspaceService


class AppServices:
    def __init__(
        self,
        *,
        settings: Settings,
        chat_run_registry: ChatRunRegistry,
        runtime_bundle: AgentScopeRuntimeBundle,
    ) -> None:
        self.settings = settings
        self.chat_run_registry = chat_run_registry
        self.runtime_principal = settings.local_runtime_principal
        self.runtime_bundle = runtime_bundle

    def redis_client(self):
        return get_redis_client()

    def session_repository(self) -> SessionRepository:
        return SessionRepository(self.redis_client())

    def team_repository(self) -> TeamRepository:
        return TeamRepository(self.redis_client())

    def workspace_repository(self) -> WorkspaceRepository:
        return WorkspaceRepository(self.redis_client())

    def state_runtime(self) -> AgentScopeSessionStateRuntime:
        return AgentScopeSessionStateRuntime(redis=self.redis_client())

    def chat_runtime(self) -> AgentScopeChatRuntime:
        return self.runtime_bundle.chat_runtime

    def confirm_runtime(self) -> ConfirmRuntime:
        return ConfirmRuntime()

    def runtime_bootstrap_service(self) -> RuntimeBootstrapService:
        return RuntimeBootstrapService(self.redis_client())

    def team_runtime(self) -> AgentScopeTeamRuntime:
        return AgentScopeTeamRuntime(self.redis_client(), self.runtime_principal)

    def workspace_service(self) -> WorkspaceService:
        return WorkspaceService(self.workspace_repository(), WorkspacePathManager())

    def workspace_query_service(self) -> WorkspaceQueryService:
        return WorkspaceQueryService(self.workspace_repository(), WorkspaceFileBrowser())

    def team_service(self) -> TeamService:
        return TeamService(self.team_repository())

    def team_query_service(self) -> TeamQueryService:
        return TeamQueryService(self.team_repository())

    def session_service(self) -> SessionService:
        return SessionService(
            session_repository=self.session_repository(),
            team_repository=self.team_repository(),
            workspace_repository=self.workspace_repository(),
            state_runtime=self.state_runtime(),
            runtime_bootstrap_service=self.runtime_bootstrap_service(),
            team_runtime=self.team_runtime(),
            runtime_principal=self.runtime_principal,
        )

    def session_query_service(self) -> SessionQueryService:
        return SessionQueryService(
            session_repository=self.session_repository(),
            team_repository=self.team_repository(),
            workspace_repository=self.workspace_repository(),
            state_runtime=self.state_runtime(),
            workspace_query_service=self.workspace_query_service(),
            team_runtime=self.team_runtime(),
            runtime_principal=self.runtime_principal,
        )

    def runtime_service(self) -> RuntimeService:
        return RuntimeService(
            session_repository=self.session_repository(),
            chat_runtime=self.chat_runtime(),
            state_runtime=self.state_runtime(),
            confirm_runtime=self.confirm_runtime(),
            chat_run_registry=self.chat_run_registry,
            session_repository_factory=self.session_repository,
            chat_runtime_factory=self.chat_runtime,
            state_runtime_factory=self.state_runtime,
            runtime_principal=self.runtime_principal,
        )
