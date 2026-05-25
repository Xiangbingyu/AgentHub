from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.models.input_event import InputEventModel, InputEventType
from app.repositories.plan_repository import PlanRepository
from app.runtime.instruction.instruction_resolver import InstructionItem, InstructionView
from app.runtime.prompt.prompt_composer import PromptComposer
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_resolver import ToolResolver


def test_prompt_composer_builds_prompt_view() -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="orchestrator",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Orchestrator",
            agent_kind="orchestrator",
        ),
        workspace_root="E:/workspace",
        role="orchestrator",
        prompt_policy={
            "system_profile": "orchestrator",
            "include_user_prompt": True,
            "user_prompt": "Always summarize next action.",
        },
        tool_policy={
            "system_toolset": "orchestrator_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_policy={"kind": "internal_llm"},
    )
    runtime.instruction_view = InstructionView(
        items=[
            InstructionItem(
                source="E:/workspace/AGENTS.md",
                content="project instructions",
                level="project",
            )
        ]
    )
    runtime.tool_view = ToolResolver(PlanRepository()).resolve(runtime)
    input_event = InputEventModel(
        input_id=uuid4(),
        run_id=runtime.agent_run.run_id,
        type=InputEventType.user_input,
        payload={"content": "hello"},
        idempotency_key="k1",
    )

    prompt_view = PromptComposer().compose(runtime, input_event)

    assert "[PROVIDER]" in prompt_view.system_prompt
    assert "[ENVIRONMENT]" in prompt_view.system_prompt
    assert "[INSTRUCTION]" in prompt_view.system_prompt
    assert "role=orchestrator" in prompt_view.system_prompt
    assert "model_visible_tools=plan_tool" in prompt_view.system_prompt
    assert "project instructions" in prompt_view.system_prompt
    assert "Always summarize next action." in prompt_view.system_prompt
    assert "orchestrator is responsible for planning and plan maintenance" in prompt_view.system_prompt
    assert "[RUNTIME_CONTEXT]" in prompt_view.context_prompt
    assert "workspace_root=E:/workspace" in prompt_view.context_prompt
    assert "input_type=user_input" in prompt_view.context_prompt
    assert prompt_view.system_sections[0].name == "provider"
