from fastapi import APIRouter

router = APIRouter(prefix="/session-page", tags=["session-page"])


@router.get("/{session_id}")
def get_session_page(session_id: str):
    return {
        "session": None,
        "main_timeline": [],
        "subtasks": [],
        "workspace_panel": {},
    }
