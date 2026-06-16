from fastapi import APIRouter

from app.api.agentscope import router as agentscope_router
from app.api.meta import router as meta_router
from app.api.session_stream import session_stream_router
from app.api.sessions import session_router
from app.api.teams import team_router
from app.api.workspaces import workspace_router
from app.config import get_settings

api_router = APIRouter()
settings = get_settings()

api_router.include_router(meta_router)
api_router.include_router(agentscope_router, prefix=settings.api_v1_prefix)
api_router.include_router(session_router, prefix=settings.api_v1_prefix)
api_router.include_router(session_stream_router, prefix=settings.api_v1_prefix)
api_router.include_router(team_router, prefix=settings.api_v1_prefix)
api_router.include_router(workspace_router, prefix=settings.api_v1_prefix)
