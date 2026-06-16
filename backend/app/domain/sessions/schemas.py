from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    name: str
    workspace_id: str
    team_id: str


class SendMessageRequest(BaseModel):
    content: str


class SubmitWaitingItemRequest(BaseModel):
    confirmed: bool
