from fastapi import FastAPI

from app.api.agent_run_create import router as agent_run_create_router
from app.api.agent_run_input import router as agent_run_input_router
from app.database.bootstrap import bootstrap_memory_store
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    bootstrap_memory_store()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/", tags=["meta"])
    def read_root() -> dict[str, str]:
        return {
            "message": f"{settings.app_name} is running",
            "environment": settings.app_env,
            "version": settings.app_version,
        }

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(agent_run_create_router)
    app.include_router(agent_run_input_router)

    return app


app = create_app()
