from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE
from agent_service.app.database.seed import ORCHESTRATOR_AGENT_ID, WORKER_AGENT_ID


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

    # 内置 agent 用固定 ID 持久化，重启/再次 bootstrap 后仍然存在。
    assert STORE.agents[ORCHESTRATOR_AGENT_ID].agent_kind == "orchestrator"
    assert STORE.agents[WORKER_AGENT_ID].agent_kind == "worker"


def test_seeded_agents_have_stable_ids() -> None:
    bootstrap_memory_store()
    first_orchestrator = STORE.agents[ORCHESTRATOR_AGENT_ID].agent_id

    # 再次 bootstrap（模拟重启）后 ID 不变，已持久化的 run 仍能解析。
    bootstrap_memory_store()
    assert STORE.agents[ORCHESTRATOR_AGENT_ID].agent_id == first_orchestrator
