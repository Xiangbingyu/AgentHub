from pydantic import BaseModel


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""
