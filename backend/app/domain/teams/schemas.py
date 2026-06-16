from pydantic import BaseModel, Field


class CreateTeamRequest(BaseModel):
    name: str
    leader_agent_id: str
    member_agent_ids: list[str] = Field(default_factory=list)
