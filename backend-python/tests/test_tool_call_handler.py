from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_registry import ToolRegistry, ToolSpec, default_invoke
from app.schemas.plan_tool import PlanToolRequest


class RecordingPlanTool:
    def __init__(self) -> None:
        self.calls = []

    def run(self, *, run_id, workspace_id, request: PlanToolRequest):
        self.calls.append(
            {
                "run_id": run_id,
                "workspace_id": workspace_id,
                "request": request,
            }
        )


class RecordingGenericTool:
    def __init__(self) -> None:
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)


def _build_runtime_bundle(toolset: dict[str, object]) -> RuntimeBundle:
    agent_id = uuid4()
    run_id = uuid4()
    workspace_id = uuid4()
    registry = ToolRegistry()
    for name, tool in toolset.items():
        registry.register(ToolSpec(name=name, tool=tool, invoke=default_invoke))

    if "plan_tool" in toolset:
        registry.register(
            ToolSpec(
                name="plan_tool",
                tool=toolset["plan_tool"],
                request_model=PlanToolRequest,
                invoke=lambda tool, runtime, request: tool.run(
                    run_id=runtime.agent_run.run_id,
                    workspace_id=runtime.agent_run.workspace_id,
                    request=request,
                ),
            )
        )

    return RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="orchestrator",
            workspace_id=workspace_id,
            root_run_id=run_id,
        ),
        agent=AgentModel(
            agent_id=agent_id,
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        ),
        workspace_root="E:/workspace",
        role="orchestrator",
        prompt_policy={"system_profile": "orchestrator"},
        tool_policy={
            "system_toolset": "orchestrator_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_policy={"kind": "internal_llm"},
        tool_registry=registry,
    )


def test_tool_registry_dispatches_plan_tool_with_nested_json_arguments() -> None:
    plan_tool = RecordingPlanTool()
    runtime_bundle = _build_runtime_bundle({"plan_tool": plan_tool})

    runtime_bundle.tool_registry.dispatch(
        runtime_bundle,
        [
            {
                "type": "function",
                "function": {
                    "name": "plan_tool",
                    "arguments": (
                        '{"plan":"{\\"title\\": \\"Execution Plan\\", \\"goal\\": \\"Ship markdown\\", '
                        '\\"summary\\": \\"Create plan\\", \\"steps\\": [{\\"step_id\\": \\"1\\", '
                        '\\"content\\": \\"Write markdown file\\", \\"status\\": \\"pending\\", '
                        '\\"priority\\": \\"high\\"}]}"}'
                    ),
                },
            }
        ],
    )

    assert len(plan_tool.calls) == 1
    call = plan_tool.calls[0]
    assert call["run_id"] == runtime_bundle.agent_run.run_id
    assert call["workspace_id"] == runtime_bundle.agent_run.workspace_id
    assert call["request"].plan.title == "Execution Plan"
    assert call["request"].plan.steps[0].content == "Write markdown file"


def test_tool_registry_uses_default_dispatch_for_other_tools() -> None:
    generic_tool = RecordingGenericTool()
    runtime_bundle = _build_runtime_bundle({"question_tool": generic_tool})

    runtime_bundle.tool_registry.dispatch(
        runtime_bundle,
        [
            {
                "type": "function",
                "function": {
                    "name": "question_tool",
                    "arguments": '{"question":"Need clarification","options":"[\\"A\\", \\"B\\"]"}',
                },
            }
        ],
    )

    assert len(generic_tool.calls) == 1
    call = generic_tool.calls[0]
    assert call["run_id"] == runtime_bundle.agent_run.run_id
    assert call["workspace_id"] == runtime_bundle.agent_run.workspace_id
    assert call["arguments"] == {
        "question": "Need clarification",
        "options": ["A", "B"],
    }
