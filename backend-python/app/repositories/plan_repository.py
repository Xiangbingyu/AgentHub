from __future__ import annotations

from uuid import UUID

from app.database.memory_store import STORE
from app.models.plan import PlanModel


class PlanRepository:
    def create(self, plan: PlanModel) -> PlanModel:
        STORE.plans[plan.run_id] = plan
        return plan

    def get_by_run_id(self, run_id: UUID) -> PlanModel | None:
        return STORE.plans.get(run_id)

    def update(self, plan: PlanModel) -> PlanModel:
        STORE.plans[plan.run_id] = plan
        return plan

    def get_raw_document(self, run_id: UUID) -> str | None:
        plan = self.get_by_run_id(run_id)
        return None if plan is None else plan.raw_document

    def save_raw_document(self, run_id: UUID, content: str) -> PlanModel | None:
        plan = self.get_by_run_id(run_id)
        if plan is None:
            return None
        plan.raw_document = content
        STORE.plans[run_id] = plan
        return plan
