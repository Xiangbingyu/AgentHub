from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.plan_repository import PlanRepository
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_registry import ToolSpec
from app.runtime.tools.tool_resolver import ToolResolver


def _build_runtime_bundle(
    *,
    role: str,
    tool_config: dict,
    executor_config: dict,
) -> RuntimeBundle:
    return RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind=role,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name=f"{role}-agent",
            agent_kind=role,
            tool_config=tool_config,
            executor_config=executor_config,
        ),
        workspace_root="E:/workspace",
        role=role,
        prompt_policy={"system_profile": role},
        tool_config=tool_config,
        executor_config=executor_config,
    )


def test_tool_resolver_builds_orchestrator_explicit_tool_view() -> None:
    runtime = _build_runtime_bundle(
        role="orchestrator",
        tool_config={
            "tools": [
                {"name": "plan_tool", "enabled": True, "options": {}},
                {"name": "delegate_tool", "enabled": True, "options": {}},
                {"name": "bash_tool", "enabled": True, "options": {}},
            ],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert view.tool_choice == "auto"
    assert view.system_toolset == "explicit"
    assert "plan_tool" in runtime.tool_registry.tools
    assert "delegate_tool" in runtime.tool_registry.tools
    assert "bash_tool" in runtime.tool_registry.tools


def test_tool_resolver_skips_disabled_explicit_tools() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_config={
            "tools": [
                {"name": "code_tool", "enabled": True, "options": {}},
                {"name": "bash_tool", "enabled": True, "options": {}},
                {"name": "plan_tool", "enabled": False, "options": {}},
            ],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["code_tool", "bash_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["code_tool", "bash_tool"]
    assert "plan_tool" not in runtime.tool_registry.tools


def test_tool_resolver_builds_worker_code_and_bash_tool_view() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_config={
            "tools": [
                {"name": "code_tool", "enabled": True, "options": {}},
                {"name": "bash_tool", "enabled": True, "options": {}},
            ],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["code_tool", "bash_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["code_tool", "bash_tool"]
    assert view.tool_choice == "auto"
    assert "code_tool" in runtime.tool_registry.tools
    assert "bash_tool" in runtime.tool_registry.tools


def test_tool_resolver_registers_skill_tool_when_enabled() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_config={
            "tools": [
                {"name": "skill_tool", "enabled": True, "options": {}},
            ],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"provider": "openai_compatible", "model": "gpt-test"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["skill_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["skill_tool"]


def test_tool_resolver_merges_mcp_runtime_tools() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_config={
            "tools": [
                {"name": "code_tool", "enabled": True, "options": {}},
            ],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"provider": "openai_compatible", "model": "gpt-test"},
    )
    runtime.mcp_runtime = {
        "enabled": True,
        "tools": [
            ToolSpec(
                name="github__search_issues",
                tool=object(),
                definition={
                    "type": "function",
                    "function": {
                        "name": "github__search_issues",
                        "description": "Search issues",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                request_model=None,
                invoke=lambda tool, runtime, request: {"ok": True},
            )
        ],
    }

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert "github__search_issues" in [item.name for item in view.system_tools]
