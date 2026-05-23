from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.models.input_event import InputEventModel, InputEventType
from app.runtime.prompt_assembler import PromptAssembler
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tool_registry import ToolRegistry


def test_prompt_assembler_builds_bundle() -> None:
    assembler = PromptAssembler()
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
        prompt_profile="orchestrator",
        tool_registry=ToolRegistry(),
    )
    input_event = InputEventModel(
        input_id=uuid4(),
        run_id=runtime.agent_run.run_id,
        type=InputEventType.user_input,
        payload={"content": "hello"},
        idempotency_key="k1",
    )

    bundle = assembler.assemble(runtime, input_event)

    assert "role=orchestrator" in bundle.system_prompt
    assert "input_type=user_input" in bundle.context_prompt
