from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE
from agent_service.app.main import app
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.models.session import SessionModel
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.schemas.agent_run_input import AgentRunInputRequest
from agent_service.app.services.agent_run_input_service import AgentRunInputService


client = TestClient(app)


def _create_active_session() -> SessionModel:
    session_workspace = SessionWorkspaceRepository().create(
        SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=uuid4(),
            name="branch-a",
            root_path="E:/workspace/branch-a",
            status="ready",
        )
    )
    session = SessionModel(
        session_id=uuid4(),
        session_workspace_id=session_workspace.session_workspace_id,
        title="demo session",
        status="active",
    )
    SessionRepository().create(session)
    return session


def test_orchestrator_input_generates_markdown_plan_file() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/agent-runs/{run_id}/input",
        json={
            "input_id": str(uuid4()),
            "type": "user_input",
            "payload": {
                "content": (
                    "Create an execution plan for implementing a markdown export feature in a Python "
                    "backend. Use the plan_tool now."
                )
            },
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}
    created_run = AgentRunRepository().get_by_id(UUID(run_id))
    assert created_run is not None
    assert created_run.status == "chatting"
    plan = PlanRepository().get_by_run_id(UUID(run_id))
    assert plan is not None
    plan_file = Path(plan.file_path)
    assert plan_file.exists()
    assert plan_file.suffix == ".md"
    assert plan_file.read_text(encoding="utf-8").strip()


def test_worker_callback_input_agent_run() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "worker")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/agent-runs/{run_id}/input",
        json={
            "input_id": str(uuid4()),
            "type": "worker_callback",
            "payload": {"summary": "done"},
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}


def test_agent_run_input_persists_domain_event_for_user_message() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(
        execute=lambda runtime_bundle, request: SimpleNamespace(content="ok", tool_calls=[], raw={})
    )

    response = service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "hello session"},
            idempotency_key=str(uuid4()),
        ),
    )

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None

    events = DomainEventRepository().list_by_session_id(run.session_id)

    assert response.status == "accepted"
    assert any(event.event_type == "session.message.appended" for event in events)


def test_agent_run_input_emits_run_lifecycle_events() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(
        execute=lambda runtime_bundle, request: SimpleNamespace(
            content="agent reply", tool_calls=[], raw={}
        )
    )

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "hello"},
            idempotency_key=str(uuid4()),
        ),
    )

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None
    events = DomainEventRepository().list_by_session_id(run.session_id)
    event_types = [event.event_type for event in events]

    assert "run.started" in event_types
    assert "run.completed" in event_types
    # agent 回复落事件，且 role 为 assistant
    assert any(
        event.event_type == "session.message.appended"
        and event.payload.get("role") == "assistant"
        and event.payload.get("content") == "agent reply"
        for event in events
    )
    # sequence_no 单调递增
    assert [event.sequence_no for event in events] == sorted(
        event.sequence_no for event in events
    )


def test_orchestrator_tool_loop_emits_tool_call_result_and_plan_events() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    plan_call = {
        "id": "call-1",
        "function": {
            "name": "plan_tool",
            "arguments": (
                '{"plan": {"title": "重构登录", "goal": "拆分登录模块", '
                '"summary": "分三步", "steps": ['
                '{"step_id": "s1", "content": "梳理现状", "status": "pending", "priority": "high"}'
                "]}}"
            ),
        },
    }

    # 第一轮：带工具思考文字 + plan_tool 调用；第二轮：无工具调用，收尾
    responses = [
        SimpleNamespace(content="我先拟个计划", tool_calls=[plan_call], raw={}),
        SimpleNamespace(content="计划已生成", tool_calls=[], raw={}),
    ]

    def _fake_execute(runtime_bundle, request):
        return responses.pop(0)

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "帮我规划重构登录模块"},
            idempotency_key=str(uuid4()),
        ),
    )

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None
    events = DomainEventRepository().list_by_session_id(run.session_id)
    event_types = [event.event_type for event in events]

    assert "agent.tool_call" in event_types
    assert "agent.tool_result" in event_types
    assert "plan.updated" in event_types

    tool_call = next(e for e in events if e.event_type == "agent.tool_call")
    assert tool_call.payload["tool_name"] == "plan_tool"
    assert tool_call.payload["tool_call_id"] == "call-1"
    assert isinstance(tool_call.payload["arguments"], dict)

    tool_result = next(e for e in events if e.event_type == "agent.tool_result")
    assert tool_result.payload["tool_name"] == "plan_tool"

    plan_event = next(e for e in events if e.event_type == "plan.updated")
    assert plan_event.payload["title"] == "重构登录"
    assert len(plan_event.payload["steps"]) == 1


def test_second_turn_replays_prior_conversation_history() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    captured: list[list] = []

    def _fake_execute(runtime_bundle, request):
        # 记录每轮 LLM 收到的消息，断言第二轮带上了历史。
        captured.append(list(request.messages))
        return SimpleNamespace(content="收到", tool_calls=[], raw={})

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "第一条消息"},
            idempotency_key=str(uuid4()),
        ),
    )
    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "第二条消息"},
            idempotency_key=str(uuid4()),
        ),
    )

    # 第一轮只有当前这条用户消息。
    first_turn = captured[0]
    assert [m.role for m in first_turn] == ["user"]
    assert first_turn[0].content == "第一条消息"

    # 第二轮应回放历史：第一条用户消息 + 第一轮 assistant 回复 + 第二条用户消息。
    second_turn = captured[1]
    contents = [(m.role, m.content) for m in second_turn]
    assert ("user", "第一条消息") in contents
    assert ("assistant", "收到") in contents
    assert ("user", "第二条消息") in contents
    assert contents[-1] == ("user", "第二条消息")


def test_tool_loop_replays_assistant_tool_call_and_bound_tool_result() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    plan_call = {
        "id": "call-1",
        "function": {
            "name": "plan_tool",
            "arguments": '{"plan": {"title": "t", "goal": "g", "summary": "s", "steps": []}}',
        },
    }
    captured = []
    responses = [
        SimpleNamespace(content="我先拟个计划", tool_calls=[plan_call], raw={}),
        SimpleNamespace(content="计划已生成", tool_calls=[], raw={}),
    ]

    def _fake_execute(runtime_bundle, request):
        captured.append(list(request.messages))
        return responses.pop(0)

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "帮我规划一下"},
            idempotency_key=str(uuid4()),
        ),
    )

    second_request_messages = captured[1]
    assistant_message = next(message for message in second_request_messages if message.role == "assistant")
    tool_message = next(message for message in second_request_messages if message.role == "tool")

    assert assistant_message.tool_calls == [plan_call]
    assert tool_message.tool_call_id == "call-1"


def test_turn_deadline_forces_terminal_reply() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    bash_call = {
        "id": "call-1",
        "function": {"name": "bash_tool", "arguments": '{"command": "echo hi", "description": "x"}'},
    }
    call_count = {"n": 0}

    def _always_tool(runtime_bundle, request):
        # 始终返回带工具调用的响应，若无时限保护会一直循环到轮次上限。
        call_count["n"] += 1
        return SimpleNamespace(content="继续执行", tool_calls=[bash_call], raw={})

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_always_tool)
    # 时限设为 0：第一轮开始前即触发强制收尾。
    service.turn_deadline_seconds = 0.0

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "请用 bash 完成"},
            idempotency_key=str(uuid4()),
        ),
    )

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None
    events = DomainEventRepository().list_by_session_id(run.session_id)
    assistant_replies = [
        e.payload.get("content")
        for e in events
        if e.event_type == "session.message.appended" and e.payload.get("role") == "assistant"
    ]
    # run 不会静默结束：至少有一条带"自动结束"字样的收尾回复。
    assert any("自动结束" in (c or "") for c in assistant_replies)


def test_agent_run_input_defaults_turn_deadline_to_10_seconds() -> None:
    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )

    assert service.turn_deadline_seconds == 10.0


def test_in_loop_llm_exception_yields_terminal_reply() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    bash_call = {
        "id": "call-1",
        "function": {"name": "bash_tool", "arguments": '{"command": "echo hi", "description": "x"}'},
    }
    calls = {"n": 0}

    def _fake_execute(runtime_bundle, request):
        # 第一次返回工具调用进入循环；第二轮（轮间 LLM 调用）抛错，模拟超时/5xx。
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(content="先跑个命令", tool_calls=[bash_call], raw={})
        raise RuntimeError("llm timeout")

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    # 不应抛异常冒泡，应正常 accepted 并给出收尾回复。
    response = service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "请用 bash 完成"},
            idempotency_key=str(uuid4()),
        ),
    )
    assert response.status == "accepted"

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None
    events = DomainEventRepository().list_by_session_id(run.session_id)
    assistant_replies = [
        e.payload.get("content")
        for e in events
        if e.event_type == "session.message.appended" and e.payload.get("role") == "assistant"
    ]
    # 轮间 LLM 抛错不再静默：有一条带"出错并自动结束"字样的收尾回复。
    assert any("出错并自动结束" in (c or "") for c in assistant_replies)


def test_tool_result_event_keeps_successful_no_output_bash_result_readable() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    bash_call = {
        "id": "call-1",
        "function": {
            "name": "bash_tool",
            "arguments": '{"command": "python -c \\\"from pathlib import Path; Path(\'created.txt\').write_text(\'ok\', encoding=\'utf-8\')\\\"", "description": "Creates a file"}',
        },
    }
    responses = [
        SimpleNamespace(content="先创建文件", tool_calls=[bash_call], raw={}),
        SimpleNamespace(content="文件已创建", tool_calls=[], raw={}),
    ]

    def _fake_execute(runtime_bundle, request):
        return responses.pop(0)

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "创建一个文件"},
            idempotency_key=str(uuid4()),
        ),
    )

    events = DomainEventRepository().list_by_session_id(session.session_id)
    tool_result = next(event for event in events if event.event_type == "agent.tool_result")
    result = tool_result.payload["result"]

    assert result["metadata"]["exit_code"] == 0
    assert "completed successfully" in result["output"].lower()


def test_cancelled_turn_stops_loop_and_defers_to_new_turn() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    bash_call = {
        "id": "call-1",
        "function": {"name": "bash_tool", "arguments": '{"command": "echo hi", "description": "x"}'},
    }

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )

    # 第一轮返回工具调用；dispatch 后在循环边界前模拟“新消息到达”置中断标志。
    def _fake_execute(runtime_bundle, request):
        # 始终带工具调用：若不中断会一直循环到上限。
        return SimpleNamespace(content="执行中", tool_calls=[bash_call], raw={})

    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    # 让 tool dispatch 后立刻置中断：用一个会在首次 dispatch 时 set 的事件。
    from agent_service.app.services.turn_coordinator import TURN_COORDINATOR

    original_begin = TURN_COORDINATOR.begin

    def _begin_and_immediately_cancel(rid):
        handle = original_begin(rid)
        # 模拟：本回合刚开始就有更晚的消息到达 → 置中断标志。
        handle.cancel_event.set()
        return handle

    TURN_COORDINATOR.begin = _begin_and_immediately_cancel
    try:
        response = service.input(
            run_id=run_id,
            payload=AgentRunInputRequest(
                input_id=uuid4(),
                type="user_input",
                payload={"content": "开始"},
                idempotency_key=str(uuid4()),
            ),
        )
    finally:
        TURN_COORDINATOR.begin = original_begin

    assert response.status == "accepted"

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None
    events = DomainEventRepository().list_by_session_id(run.session_id)
    interrupted = [
        e
        for e in events
        if e.event_type == "run.completed" and e.payload.get("status") == "interrupted"
    ]
    # 被中断的回合必须显式收尾，避免前端永远等待 loading。
    assert interrupted
    # 也没有"自动结束/出错"之类的收尾回复——它只是让位。
    terminal_like = [
        e.payload.get("content", "")
        for e in events
        if e.event_type == "session.message.appended" and e.payload.get("role") == "assistant"
    ]
    assert not any("自动结束" in c for c in terminal_like)


def test_cancelled_turn_during_blocking_followup_llm_call_emits_interrupted() -> None:
    import threading
    import time

    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    bash_call = {
        "id": "call-1",
        "function": {
            "name": "bash_tool",
            "arguments": '{"command": "echo hi", "description": "x"}',
        },
    }
    calls = {"n": 0}

    def _fake_execute(runtime_bundle, request):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(content="先执行命令", tool_calls=[bash_call], raw={})
        time.sleep(10)
        return SimpleNamespace(content="收尾完成", tool_calls=[], raw={})

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(execute=_fake_execute)

    from agent_service.app.services.turn_coordinator import TURN_COORDINATOR

    original_begin = TURN_COORDINATOR.begin

    def _begin_and_cancel_during_followup(rid):
        handle = original_begin(rid)
        threading.Timer(0.3, handle.cancel_event.set).start()
        return handle

    TURN_COORDINATOR.begin = _begin_and_cancel_during_followup
    started = time.monotonic()
    try:
        response = service.input(
            run_id=run_id,
            payload=AgentRunInputRequest(
                input_id=uuid4(),
                type="user_input",
                payload={"content": "开始执行"},
                idempotency_key=str(uuid4()),
            ),
        )
    finally:
        TURN_COORDINATOR.begin = original_begin
    elapsed = time.monotonic() - started

    assert response.status == "accepted"
    assert elapsed < 5, f"blocking LLM call should yield quickly after interrupt, got {elapsed:.1f}s"

    events = DomainEventRepository().list_by_session_id(session.session_id)
    interrupted = [
        e
        for e in events
        if e.event_type == "run.completed" and e.payload.get("status") == "interrupted"
    ]
    assert interrupted
