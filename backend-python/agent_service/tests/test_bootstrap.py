from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE


def test_bootstrap_clears_memory_store() -> None:
    STORE.agent_runs.clear()
    STORE.input_events.clear()
    STORE.subtasks.clear()
    STORE.plans.clear()
    STORE.agent_runs["dummy"] = object()  # type: ignore[assignment]

    bootstrap_memory_store()

    assert STORE.agent_runs == {}
    assert STORE.input_events == {}
    assert STORE.subtasks == {}
    assert STORE.plans == {}


def test_bootstrap_seeds_agents() -> None:
    bootstrap_memory_store()

    assert len(STORE.agents) == 2
    assert {agent.agent_kind for agent in STORE.agents.values()} == {"orchestrator", "worker"}
