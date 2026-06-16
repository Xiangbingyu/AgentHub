from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import ApiError
from app.api.router import api_router
from app.application.services import AppServices
from app.config import get_settings
from app.runtime.agentscope.chat_run_registry import ChatRunRegistry
from app.runtime.agentscope.runtime_bundle import AgentScopeRuntimeBundle


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    services = app.state.services
    await services.runtime_bundle.__aenter__()
    await services.team_service().ensure_default_team()
    try:
        yield
    finally:
        await services.runtime_bundle.__aexit__()
        await services.chat_run_registry.__aexit__()


def create_app() -> FastAPI:
    settings = get_settings()
    chat_run_registry = ChatRunRegistry()
    runtime_bundle = AgentScopeRuntimeBundle(
        redis_url=settings.redis_url,
        workspace_base_dir=settings.workspace_base_dir,
        chat_run_registry=chat_run_registry,
    )
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.services = AppServices(
        settings=settings,
        chat_run_registry=chat_run_registry,
        runtime_bundle=runtime_bundle,
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        del request
        return JSONResponse(status_code=exc.status_code, content=exc.to_response())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
