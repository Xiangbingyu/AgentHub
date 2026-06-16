from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceRecord(BaseModel):
    workspace_id: str
    name: str
    root_path: str
    description: str = ""
    backend_type: str = "local"
    status: str = "ready"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
