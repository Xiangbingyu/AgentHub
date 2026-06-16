from __future__ import annotations

from app.infrastructure.storage.team_repository import TeamRepository


class TeamQueryService:
    def __init__(self, repository: TeamRepository) -> None:
        self._repository = repository

    async def list_teams(self) -> dict:
        teams = await self._repository.list_teams()
        return {"teams": [team.model_dump(mode="json") for team in teams]}
