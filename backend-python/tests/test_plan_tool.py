from uuid import uuid4

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan_tool import PlanSnapshot, PlanStepPayload, PlanStepStatus, PlanToolRequest
from app.tools.plan_tool import PlanTool


def test_plan_tool_writes_plan_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    bootstrap_memory_store()

    plan_tool = PlanTool(PlanRepository())
    run_id = uuid4()
    workspace_id = uuid4()

    response = plan_tool.run(
        run_id=run_id,
        workspace_id=workspace_id,
        request=PlanToolRequest(
            plan=PlanSnapshot(
                title="Implement input loop",
                goal="Build the input loop skeleton",
                summary="Initial plan",
                steps=[
                    PlanStepPayload(
                        step_id="step-1",
                        content="Create input schema",
                        status=PlanStepStatus.completed,
                        priority="high",
                    )
                ],
            )
        ),
    )

    assert response.status == "updated"
    assert response.file_path.endswith(".execution-plan.md")
    assert response.plan_id is not None
    assert STORE.plans[run_id].title == "Implement input loop"
    assert STORE.plans[run_id].steps[0]["content"] == "Create input schema"
    plan_file = tmp_path / ".AgentHub" / "plans" / f"{run_id}.execution-plan.md"
    assert plan_file.exists()
    assert "# Implement input loop" in plan_file.read_text(encoding="utf-8")
