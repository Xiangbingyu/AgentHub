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
        snapshot.setdefault("tool_config", agent.tool_config.model_dump())
        snapshot.setdefault("skill_config", agent.skill_config.model_dump())
        snapshot.setdefault("mcp_config", agent.mcp_config.model_dump())
        snapshot.setdefault("executor_config", agent.executor_config.model_dump())
        return snapshot

    def build_default_snapshot(self, agent: AgentModel) -> dict[str, object]:
        return {
            "role": agent.role,
            "prompt_policy": dict(agent.prompt_policy),
            "tool_config": agent.tool_config.model_dump(),
            "skill_config": agent.skill_config.model_dump(),
            "mcp_config": agent.mcp_config.model_dump(),
            "executor_config": agent.executor_config.model_dump(),
        }
