from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(tags=["meta"])


@router.get("/")
def read_root(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env,
        "version": settings.app_version,
    }


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
