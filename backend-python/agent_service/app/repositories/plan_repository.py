from __future__ import annotations

from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.plan import PlanModel


class PlanRepository:
    def create(self, plan: PlanModel) -> PlanModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO plans (run_id, payload) VALUES (?, ?)",
            (str(plan.run_id), plan.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return plan

    def get_by_run_id(self, run_id: UUID) -> PlanModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM plans WHERE run_id = ?",
            (str(run_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return PlanModel.model_validate_json(row[0])

    def update(self, plan: PlanModel) -> PlanModel:
        return self.create(plan)

    def get_raw_document(self, run_id: UUID) -> str | None:
        plan = self.get_by_run_id(run_id)
        return None if plan is None else plan.raw_document

    def save_raw_document(self, run_id: UUID, content: str) -> PlanModel | None:
        plan = self.get_by_run_id(run_id)
        if plan is None:
            return None
        plan.raw_document = content
        return self.update(plan)
