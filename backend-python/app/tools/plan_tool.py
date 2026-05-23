from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.models.plan import PlanModel
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan_tool import PlanSnapshot, PlanStepPayload, PlanToolRequest, PlanToolResponse


class PlanTool:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self.plan_repository = plan_repository

    def run(self, *, run_id: UUID, workspace_id: UUID, request: PlanToolRequest) -> PlanToolResponse:
        snapshot = request.plan
        plan = self.plan_repository.get_by_run_id(run_id)
        if plan is None:
            plan = PlanModel(
                plan_id=uuid4(),
                run_id=run_id,
                workspace_id=workspace_id,
                file_path=self._build_plan_file_path(run_id),
            )
            self.plan_repository.create(plan)

        plan.title = snapshot.title
        plan.goal = snapshot.goal
        plan.summary = snapshot.summary
        plan.steps = [step.model_dump() for step in snapshot.steps]
        plan.status = self._derive_status(snapshot.steps)
        plan.updated_at = datetime.now(timezone.utc)
        plan.file_path = self._build_plan_file_path(run_id)
        plan.raw_document = self._render_markdown(run_id=run_id, snapshot=snapshot, updated_at=plan.updated_at)

        self.plan_repository.update(plan)
        self._write_plan_file(plan.file_path, plan.raw_document)

        return PlanToolResponse(
            plan_id=plan.plan_id,
            status="updated",
            file_path=plan.file_path,
            summary="Plan updated and synced",
        )

    def _build_plan_file_path(self, run_id: UUID) -> str:
        return str(Path.cwd() / ".AgentHub" / "plans" / f"{run_id}.execution-plan.md")

    def _derive_status(self, steps: list[PlanStepPayload]) -> str:
        if not steps:
            return "pending"

        statuses = {step.status for step in steps}
        if statuses == {"completed"}:
            return "completed"
        if statuses == {"cancelled"}:
            return "cancelled"
        if "in_progress" in statuses:
            return "in_progress"
        if statuses == {"pending"}:
            return "pending"
        return "in_progress"

    def _render_markdown(self, *, run_id: UUID, snapshot: PlanSnapshot, updated_at: datetime) -> str:
        step_lines = [self._render_step(step) for step in snapshot.steps] or ["- [ ] (empty)"]
        return "\n".join(
            [
                f"# {snapshot.title}",
                "",
                "## Goal",
                snapshot.goal,
                "",
                "## Summary",
                snapshot.summary,
                "",
                "## Steps",
                *step_lines,
                "",
                "## Meta",
                f"- Run ID: {run_id}",
                f"- Updated At: {updated_at.isoformat()}",
            ]
        )

    def _render_step(self, step: PlanStepPayload) -> str:
        checkbox = {
            "pending": "[ ]",
            "in_progress": "[~]",
            "completed": "[x]",
            "cancelled": "[-]",
        }[step.status.value]
        return f"- {checkbox} {step.content}"

    def _write_plan_file(self, file_path: str, content: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
