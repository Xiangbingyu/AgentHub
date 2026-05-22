from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
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

    return app


app = create_app()
