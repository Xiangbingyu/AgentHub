from fastapi import FastAPI

from app.api.session_page import router as session_page_router
from app.api.session_stream import router as session_stream_router
from app.api.workspace_page import router as workspace_page_router


def create_app() -> FastAPI:
    app = FastAPI(title="gateway_service", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(workspace_page_router)
    app.include_router(session_page_router)
    app.include_router(session_stream_router)
    return app


app = create_app()
