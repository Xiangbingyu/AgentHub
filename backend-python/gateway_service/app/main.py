from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway_service.app.api.read_proxy import router as read_proxy_router
from gateway_service.app.api.session_page import router as session_page_router
from gateway_service.app.api.session_stream import router as session_stream_router
from gateway_service.app.api.workspace_page import router as workspace_page_router
from gateway_service.app.api.write_proxy import router as write_proxy_router
from gateway_service.app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="gateway_service", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(workspace_page_router)
    app.include_router(session_page_router)
    app.include_router(session_stream_router)
    app.include_router(read_proxy_router)
    app.include_router(write_proxy_router)
    return app


app = create_app()
