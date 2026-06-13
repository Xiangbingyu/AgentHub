from pathlib import Path
from uuid import uuid4

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.models.agent import AgentModel
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.runtime.runtime_assembler import RuntimeBundle
from agent_service.app.runtime.tools.tool_registry import ToolRegistry
from agent_service.app.runtime.workspace.workspace_session import WorkspaceSession
from agent_service.app.schemas.plan_tool import PlanSnapshot, PlanStepPayload, PlanStepStatus, PlanToolRequest
from agent_service.app.tools.plan_tool import PlanTool


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
    plan = PlanRepository().get_by_run_id(run_id)
    assert plan is not None
    assert plan.title == "Implement input loop"
    assert plan.steps[0]["content"] == "Create input schema"
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
        tool_config={
            "tools": [{"name": "plan_tool", "enabled": True, "options": {}}],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
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
