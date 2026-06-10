from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.policy.executor_policy_resolver import ExecutorPolicyResolver
from app.runtime.policy.prompt_policy_resolver import PromptPolicyResolver
from app.runtime.policy.tool_policy_resolver import ToolPolicyResolver
from app.runtime.snapshot.runtime_snapshot_resolver import RuntimeSnapshotResolver


def test_runtime_snapshot_resolver_builds_defaults_from_agent() -> None:
    agent = AgentModel(
        agent_id=uuid4(),
        agent_name="orchestrator",
        agent_kind="orchestrator",
        prompt_policy={"user_prompt": "custom"},
        tool_config={
            "tools": [
                {"name": "plan_tool"},
                {"name": "delegate_tool"},
                {"name": "bash_tool"},
            ],
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )
    agent_run = AgentRunModel(
        run_id=uuid4(),
        agent_id=agent.agent_id,
        agent_kind=agent.agent_kind,
        workspace_id=uuid4(),
        root_run_id=uuid4(),
    )

    snapshot = RuntimeSnapshotResolver().resolve(agent_run, agent)

    assert snapshot["role"] == "orchestrator"
    assert snapshot["prompt_policy"]["user_prompt"] == "custom"
    assert [item["name"] for item in snapshot["tool_config"]["tools"]] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert snapshot["executor_config"]["kind"] == "internal_llm"
    assert snapshot["executor_config"]["model"] == "gpt-test"
    assert "tool_policy" not in snapshot
    assert "executor_policy" not in snapshot


def test_executor_config_resolver_builds_internal_defaults() -> None:
    runtime_snapshot = {
        "role": "worker",
        "prompt_policy": {},
        "tool_config": {},
        "executor_config": {"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    }
    executor_policy = ExecutorPolicyResolver().resolve(runtime_snapshot)

    prompt_policy = PromptPolicyResolver().resolve(runtime_snapshot, executor_policy=executor_policy)
    tool_policy = ToolPolicyResolver().resolve(
        runtime_snapshot,
        role="worker",
        executor_policy=executor_policy,
    )

    assert prompt_policy["system_profile"] == "worker"
    assert executor_policy == {
        "kind": "internal_llm",
        "provider": "openai_compatible",
        "model": "gpt-test",
        "framework": None,
        "command": None,
        "timeout_seconds": 300,
        "framework_options": {},
    }
    assert tool_policy["tools"] == []
    assert tool_policy["model_tools_enabled"] is True
    assert tool_policy["runtime_tools_enabled"] is True


def test_tool_policy_resolver_uses_empty_tool_list_defaults() -> None:
    tool_policy = ToolPolicyResolver().resolve(
        {"tool_config": {}},
        role="worker",
        executor_policy={"kind": "internal_llm"},
    )

    assert tool_policy == {
        "tools": [],
        "user_tools": [],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
        "command_policies": {"bash": {"*": "allow"}},
    }


def test_tool_policy_resolver_preserves_runtime_snapshot_tool_items() -> None:
    tool_policy = ToolPolicyResolver().resolve(
        {
            "tool_config": {
                "tools": [{"name": "code_tool", "enabled": True, "options": {}}],
                "command_policies": {
                    "bash": {
                        "*": "deny",
                        "git status *": "allow",
                    }
                },
            }
        },
        role="worker",
        executor_policy={"kind": "internal_llm"},
    )

    assert tool_policy["tools"] == [{"name": "code_tool", "enabled": True, "options": {}}]
    assert tool_policy["command_policies"] == {
        "bash": {
            "*": "deny",
            "git status *": "allow",
        }
    }
