from pathlib import Path
from uuid import uuid4

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.plan_repository import PlanRepository
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_registry import ToolRegistry
from app.runtime.workspace.workspace_session import WorkspaceSession
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


def test_plan_tool_writes_plan_inside_workspace(tmp_path: Path) -> None:
    bootstrap_memory_store()
    tool = PlanTool(PlanRepository())
    run_id = uuid4()
    workspace_id = uuid4()
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=run_id,
            agent_id=uuid4(),
            agent_kind="orchestrator",
            workspace_id=workspace_id,
            root_run_id=run_id,
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        ),
        workspace_root=str(tmp_path),
        role="orchestrator",
        prompt_policy={"system_profile": "orchestrator"},
        tool_policy={
            "system_toolset": "orchestrator_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_policy={"kind": "internal_llm"},
        tool_registry=ToolRegistry(),
        workspace_session=WorkspaceSession(str(tmp_path)),
    )

    response = tool.run(
        run_id=run_id,
        workspace_id=workspace_id,
        runtime=runtime,
        request=PlanToolRequest(
            plan=PlanSnapshot(
                title="Execution Plan",
                goal="Ship workspace session",
                summary="Create shared workspace access",
                steps=[
                    PlanStepPayload(
                        step_id="1",
                        content="write code",
                        status=PlanStepStatus.pending,
                        priority="high",
                    )
                ],
            )
        ),
    )

    output_path = tmp_path / ".AgentHub" / "plans" / f"{run_id}.execution-plan.md"
    assert output_path.exists()
    assert response.file_path == str(output_path)
