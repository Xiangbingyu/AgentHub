from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.agentscope_service import get_runtime_status

router = APIRouter(prefix="/agentscope", tags=["agentscope"])


@router.get("/status")
def read_agentscope_status(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return get_runtime_status(settings)
