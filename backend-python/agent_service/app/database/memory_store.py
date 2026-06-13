from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
from uuid import UUID

from agent_service.app.models.agent import AgentModel
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.models.input_event import InputEventModel
from agent_service.app.models.plan import PlanModel
from agent_service.app.models.subtask import SubtaskModel


@dataclass
class InMemoryStore:
    agents: Dict[UUID, AgentModel] = field(default_factory=dict)
    agent_runs: Dict[UUID, AgentRunModel] = field(default_factory=dict)
    input_events: Dict[UUID, InputEventModel] = field(default_factory=dict)
    subtasks: Dict[UUID, SubtaskModel] = field(default_factory=dict)
    plans: Dict[UUID, PlanModel] = field(default_factory=dict)

    def reset(self) -> None:
        self.agents.clear()
        self.agent_runs.clear()
        self.input_events.clear()
        self.subtasks.clear()
        self.plans.clear()


STORE = InMemoryStore()
