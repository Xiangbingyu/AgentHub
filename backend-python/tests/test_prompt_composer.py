from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.models.input_event import InputEventModel, InputEventType
from app.repositories.plan_repository import PlanRepository
from app.runtime.instruction.instruction_resolver import InstructionItem, InstructionView
from app.runtime.prompt.prompt_composer import PromptComposer
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_resolver import ToolResolver
from app.runtime.workspace.workspace_session import WorkspaceSession


def test_prompt_composer_builds_prompt_view() -> None:
    tool_config = {
        "tools": [
            {"name": "plan_tool", "enabled": True, "options": {}},
            {"name": "delegate_tool", "enabled": True, "options": {}},
            {"name": "bash_tool", "enabled": True, "options": {}},
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }
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
            tool_config=tool_config,
        ),
        workspace_root="E:/workspace",
        role="orchestrator",
        prompt_policy={
            "system_profile": "orchestrator",
            "include_user_prompt": True,
            "user_prompt": "Always summarize next action.",
        },
        tool_config=tool_config,
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
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
    assert "system_toolset=" not in prompt_view.system_prompt
    assert "model_visible_tools=plan_tool,delegate_tool,bash_tool" in prompt_view.system_prompt
    assert "project instructions" in prompt_view.system_prompt
    assert "Always summarize next action." in prompt_view.system_prompt
    assert "orchestrator is responsible for planning and plan maintenance" in prompt_view.system_prompt
    assert "bash_tool" in prompt_view.system_prompt
    assert "must call bash_tool" in prompt_view.system_prompt
    assert "[RUNTIME_CONTEXT]" in prompt_view.context_prompt
    assert "workspace_root=E:/workspace" in prompt_view.context_prompt
    assert "input_type=user_input" in prompt_view.context_prompt
    assert prompt_view.system_sections[0].name == "provider"


def test_prompt_composer_lists_worker_code_tool_as_model_visible() -> None:
    tool_config = {
        "tools": [
            {"name": "code_tool", "enabled": True, "options": {}},
            {"name": "bash_tool", "enabled": True, "options": {}},
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Worker",
            agent_kind="worker",
            tool_config=tool_config,
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_policy={"system_profile": "worker"},
        tool_config=tool_config,
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
        workspace_session=WorkspaceSession("E:/Github/AgentHub-weon/backend-python"),
    )
    runtime.tool_view = ToolResolver(PlanRepository()).resolve(runtime)
    input_event = InputEventModel(
        input_id=uuid4(),
        run_id=runtime.agent_run.run_id,
        type=InputEventType.user_input,
        payload={"content": "write code"},
        idempotency_key="k2",
    )

    prompt_view = PromptComposer().compose(runtime, input_event)

    assert "system_toolset=" not in prompt_view.system_prompt
    assert "model_visible_tools=code_tool,bash_tool" in prompt_view.system_prompt
    assert "code_tool" in prompt_view.system_prompt
    assert "bash_tool" in prompt_view.system_prompt
    assert "move" in prompt_view.system_prompt or "rename" in prompt_view.system_prompt
    assert "first action" in prompt_view.system_prompt


def test_prompt_composer_includes_available_skills_block() -> None:
    tool_config = {
        "tools": [
            {"name": "code_tool", "enabled": True, "options": {}},
            {"name": "bash_tool", "enabled": True, "options": {}},
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Worker",
            agent_kind="worker",
            tool_config=tool_config,
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_policy={"system_profile": "worker"},
        tool_config=tool_config,
        executor_config={"provider": "openai_compatible", "model": "gpt-test"},
        skill_config={"builtins_enabled": True, "paths": [], "include_global": False, "allowed_skills": []},
        mcp_config={"enabled": False, "servers": []},
        skill_registry=type(
            "FakeSkillRegistry",
            (),
            {
                "render_available_skills": lambda self: "<available_skills><skill><name>debugging</name><description>Debug failures</description></skill></available_skills>"
            },
        )(),
        mcp_runtime={"enabled": False, "tools": []},
        workspace_session=WorkspaceSession("E:/Github/AgentHub-weon/backend-python"),
    )
    runtime.tool_view = ToolResolver(PlanRepository()).resolve(runtime)
    input_event = InputEventModel(
        input_id=uuid4(),
        run_id=runtime.agent_run.run_id,
        type=InputEventType.user_input,
        payload={"content": "write code"},
        idempotency_key="k3",
    )

    prompt_view = PromptComposer().compose(runtime, input_event)

    assert "<available_skills>" in prompt_view.system_prompt
    assert "debugging" in prompt_view.system_prompt
