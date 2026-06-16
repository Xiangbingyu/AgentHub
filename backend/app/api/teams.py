from __future__ import annotations

from fastapi import APIRouter, Request

from app.domain.teams.schemas import CreateTeamRequest

team_router = APIRouter(prefix="/teams", tags=["teams"])


@team_router.get("")
async def list_teams(request: Request) -> dict:
    services = request.app.state.services
    writer = services.team_service()
    await writer.ensure_default_team()
    service = services.team_query_service()
    return await service.list_teams()


@team_router.post("", status_code=201)
async def create_team(body: CreateTeamRequest, request: Request) -> dict:
    service = request.app.state.services.team_service()
    record = await service.create_team(
        name=body.name,
        leader_agent_id=body.leader_agent_id,
        member_agent_ids=body.member_agent_ids,
    )
    return record.model_dump(mode="json")
