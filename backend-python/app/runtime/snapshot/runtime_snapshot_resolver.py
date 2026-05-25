from __future__ import annotations

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel


class RuntimeSnapshotResolver:
    def resolve(self, agent_run: AgentRunModel, agent: AgentModel) -> dict[str, object]:
        snapshot = dict(agent_run.runtime_snapshot)
        if not snapshot:
            snapshot = self.build_default_snapshot(agent)

        snapshot.setdefault("role", agent.role)
        snapshot.setdefault("prompt_policy", dict(agent.prompt_policy))
        snapshot.setdefault("tool_policy", dict(agent.tool_policy))
        snapshot.setdefault("executor_policy", dict(agent.executor_policy))
        return snapshot

    def build_default_snapshot(self, agent: AgentModel) -> dict[str, object]:
        return {
            "role": agent.role,
            "prompt_policy": dict(agent.prompt_policy),
            "tool_policy": dict(agent.tool_policy),
            "executor_policy": dict(agent.executor_policy),
        }
