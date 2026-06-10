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
        tool_policy={"system_toolset": "orchestrator_default"},
        executor_policy={"kind": "internal_llm"},
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
    assert snapshot["tool_policy"]["system_toolset"] == "orchestrator_default"


def test_prompt_and_tool_policy_resolvers_apply_framework_worker_defaults() -> None:
    runtime_snapshot = {
        "role": "worker",
        "prompt_policy": {},
        "tool_policy": {},
        "executor_policy": {"kind": "framework_cli", "framework": "claude"},
    }
    executor_policy = ExecutorPolicyResolver().resolve(runtime_snapshot)

    prompt_policy = PromptPolicyResolver().resolve(runtime_snapshot, executor_policy=executor_policy)
    tool_policy = ToolPolicyResolver().resolve(
        runtime_snapshot,
        role="worker",
        executor_policy=executor_policy,
    )

    assert prompt_policy["system_profile"] == "framework_worker"
    assert tool_policy["system_toolset"] == "none"
    assert tool_policy["model_tools_enabled"] is False
    assert tool_policy["runtime_tools_enabled"] is False


def test_tool_policy_resolver_includes_default_bash_policy_rules() -> None:
    tool_policy = ToolPolicyResolver().resolve(
        {"tool_policy": {}},
        role="worker",
        executor_policy={"kind": "internal_llm"},
    )

    assert tool_policy["command_policies"] == {"bash": {"*": "allow"}}


def test_tool_policy_resolver_preserves_runtime_snapshot_command_policies() -> None:
    tool_policy = ToolPolicyResolver().resolve(
        {
            "tool_policy": {
                "command_policies": {
                    "bash": {
                        "*": "deny",
                        "git status *": "allow",
                    }
                }
            }
        },
        role="worker",
        executor_policy={"kind": "internal_llm"},
    )

    assert tool_policy["command_policies"] == {
        "bash": {
            "*": "deny",
            "git status *": "allow",
        }
    }
