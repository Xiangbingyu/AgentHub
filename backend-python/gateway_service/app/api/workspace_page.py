from fastapi import APIRouter

router = APIRouter(prefix="/workspace-page", tags=["workspace-page"])


@router.get("/{source_workspace_id}")
def get_workspace_page(source_workspace_id: str):
    return {
        "source_workspace": None,
        "session_workspaces": [],
    }
