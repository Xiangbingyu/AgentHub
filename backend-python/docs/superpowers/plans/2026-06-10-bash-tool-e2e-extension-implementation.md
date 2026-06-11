# Bash Tool E2E Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `bash_tool` from runtime/tool-level coverage to orchestrator and delegated-worker end-to-end coverage, while permanently exposing `bash_tool` to orchestrator runs.

**Architecture:** First update the orchestrator runtime contract so `bash_tool` is permanently present in `orchestrator_default`, and align existing visibility tests to that new baseline. Then tighten orchestrator and worker prompt guidance so the model is explicitly told when to use `bash_tool`, add one deterministic delegate-chain file-move test, and finally add two opt-in real internal LLM E2E tests that verify actual `bash_tool` selection in orchestrator and worker flows.

**Tech Stack:** Python 3.13, pytest, Pydantic, existing runtime/tool registry architecture, existing internal LLM executor path

---

## File Map

- Modify: `app/runtime/tools/tool_resolver.py`
  - Permanently register `bash_tool` in `orchestrator_default`.
- Modify: `app/runtime/prompt/mode/orchestrator_mode_prompt.py`
  - Tell orchestrators to use `bash_tool` for command-backed inspection before planning.
- Modify: `app/runtime/prompt/mode/worker_mode_prompt.py`
  - Keep the `code_tool` write rule and add a narrow `bash_tool` relocation rule.
- Modify: `tests/test_runtime_assembler.py`
  - Align orchestrator runtime expectations with the new default toolset.
- Modify: `tests/test_tool_resolver.py`
  - Align orchestrator tool resolver expectations with the new default toolset.
- Create: `tests/test_delegate_chain_internal_bash_tool.py`
  - Deterministic delegate-chain test for worker `bash_tool` file move.
- Modify: `tests/test_delegate_chain_e2e_internal_llm.py`
  - Add real internal LLM orchestrator inspection E2E and delegated worker move E2E.

### Task 1: Expose `bash_tool` to orchestrators and align runtime visibility tests

**Files:**
- Modify: `app/runtime/tools/tool_resolver.py`
- Modify: `tests/test_runtime_assembler.py`
- Modify: `tests/test_tool_resolver.py`
- Test: `tests/test_runtime_assembler.py`
- Test: `tests/test_tool_resolver.py`

- [ ] **Step 1: Write the failing orchestrator visibility tests**

Update `tests/test_runtime_assembler.py` so `test_orchestrator_runtime_exposes_tool_registry_contract()` expects:

```python
    assert set(runtime.tool_registry.tools) == {"plan_tool", "delegate_tool", "bash_tool"}
    assert len(definitions) == 3
    assert [item["function"]["name"] for item in definitions] == ["plan_tool", "delegate_tool", "bash_tool"]
```

Update `tests/test_tool_resolver.py` so `test_tool_resolver_builds_orchestrator_system_tool_view()` expects:

```python
    assert [item.name for item in view.system_tools] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert "bash_tool" in runtime.tool_registry.tools
```

- [ ] **Step 2: Run the visibility tests to verify they fail**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_assembler.py::test_orchestrator_runtime_exposes_tool_registry_contract tests/test_tool_resolver.py::test_tool_resolver_builds_orchestrator_system_tool_view -v`
Expected: FAIL because `orchestrator_default` does not register `bash_tool` yet.

- [ ] **Step 3: Register `bash_tool` in `orchestrator_default`**

Update the `if system_toolset == "orchestrator_default":` block in `app/runtime/tools/tool_resolver.py` to include:

```python
            registry.register(
                ToolSpec(
                    name="bash_tool",
                    tool=BashTool(),
                    definition=build_bash_tool_definition(),
                    request_model=BashToolRequest,
                    invoke=default_invoke,
                )
            )
```

Place it after the existing `delegate_tool` registration so the orchestrator tool order becomes:

```python
["plan_tool", "delegate_tool", "bash_tool"]
```

- [ ] **Step 4: Run the orchestrator visibility tests to verify they pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_assembler.py::test_orchestrator_runtime_exposes_tool_registry_contract tests/test_tool_resolver.py::test_tool_resolver_builds_orchestrator_system_tool_view -v`
Expected: PASS

- [ ] **Step 5: Commit the orchestrator tool exposure change**

```bash
git add app/runtime/tools/tool_resolver.py tests/test_runtime_assembler.py tests/test_tool_resolver.py
git commit -m "feat(runtime): expose bash tool to orchestrators"
```

### Task 2: Tighten orchestrator and worker prompt guidance for `bash_tool`

**Files:**
- Modify: `app/runtime/prompt/mode/orchestrator_mode_prompt.py`
- Modify: `app/runtime/prompt/mode/worker_mode_prompt.py`
- Modify: `tests/test_prompt_composer.py`
- Test: `tests/test_prompt_composer.py`

- [ ] **Step 1: Write the failing prompt expectations**

Add prompt assertions to `tests/test_prompt_composer.py`:

```python
def test_prompt_composer_includes_orchestrator_bash_tool_guidance() -> None:
    prompt = build_orchestrator_mode_prompt()

    assert "bash_tool" in prompt
    assert "must call bash_tool" in prompt


def test_prompt_composer_includes_worker_bash_tool_move_guidance() -> None:
    prompt = build_worker_mode_prompt()

    assert "code_tool" in prompt
    assert "bash_tool" in prompt
    assert "move" in prompt or "rename" in prompt
```

If the file already uses a different prompt-composer entry point, adapt the assertions to that existing helper rather than adding a second prompt path.

- [ ] **Step 2: Run the prompt tests to verify they fail**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_prompt_composer.py -v`
Expected: FAIL because the current prompt strings do not mention `bash_tool`.

- [ ] **Step 3: Update the orchestrator and worker prompt builders**

Replace `app/runtime/prompt/mode/orchestrator_mode_prompt.py` with:

```python
from __future__ import annotations


def build_orchestrator_mode_prompt() -> str:
    return (
        "orchestrator is responsible for planning and plan maintenance; "
        "when planning depends on command-line inspection of files, directories, or other workspace state, "
        "you must call bash_tool to obtain that information and must not assume command output in plain text"
    )
```

Update `app/runtime/prompt/mode/worker_mode_prompt.py` to:

```python
from __future__ import annotations


def build_worker_mode_prompt() -> str:
    return (
        "worker is responsible for task execution; when asked to create, update, or delete files, "
        "you must use code_tool to perform the file change and must not only describe the change in text; "
        "write the intended content to disk and do not leave an empty placeholder file; "
        "when a task explicitly requires shell-based file relocation, copy, or rename operations, use bash_tool"
    )
```

- [ ] **Step 4: Run the prompt tests to verify they pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_prompt_composer.py -v`
Expected: PASS

- [ ] **Step 5: Commit the prompt guidance update**

```bash
git add app/runtime/prompt/mode/orchestrator_mode_prompt.py app/runtime/prompt/mode/worker_mode_prompt.py tests/test_prompt_composer.py
git commit -m "feat(prompt): add bash tool usage guidance"
```

### Task 3: Add deterministic delegated worker `bash_tool` file-move coverage

**Files:**
- Create: `tests/test_delegate_chain_internal_bash_tool.py`
- Test: `tests/test_delegate_chain_internal_bash_tool.py`

- [ ] **Step 1: Write the failing scripted delegate-chain test**

Create `tests/test_delegate_chain_internal_bash_tool.py` with:

```python
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.llm.llm_executor import AgentExecutorFactory
from app.llm.llm_types import LlmResponse
from app.models.agent import AgentModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.agent_run_create import AgentRunCreateRequest
from app.schemas.agent_run_input import AgentRunInputRequest
from app.services.agent_run_create_service import AgentRunCreateService
from app.services.agent_run_input_service import AgentRunInputService


class SequencedExecutor:
    def __init__(self, responses: list[LlmResponse]) -> None:
        self.responses = responses
        self.calls = []

    def execute(self, runtime, request):
        self.calls.append(
            {
                "role": runtime.role,
                "run_id": runtime.agent_run.run_id,
                "tools": [tool["function"]["name"] for tool in request.tools],
                "content": request.messages[0].content if request.messages else "",
            }
        )
        if not self.responses:
            raise AssertionError("no response prepared for executor")
        return self.responses.pop(0)


def test_delegate_chain_internal_worker_uses_bash_tool_to_move_workspace_file(monkeypatch) -> None:
    bootstrap_memory_store()

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()

    worker_agent = agent_repository.create(
        AgentModel(agent_id=uuid4(), agent_name="Internal Worker", agent_kind="worker")
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(agent_id=uuid4(), agent_name="Internal Orchestrator", agent_kind="orchestrator")
    )

    repo_root = Path(__file__).resolve().parents[1]
    source_path = repo_root / ".AgentHub" / "tests" / "test1" / "bash_tool_test1.md"
    target_path = repo_root / ".AgentHub" / "tests" / "test2" / "bash_tool_test1.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()

    executor = SequencedExecutor(
        responses=[
            LlmResponse(
                content="planned and delegated",
                tool_calls=[
                    {
                        "id": "tool_1",
                        "type": "function",
                        "function": {
                            "name": "plan_tool",
                            "arguments": (
                                '{"plan":{"title":"Move file","goal":"Move delegated test file",'
                                '"summary":"Delegate file move to worker","steps":[{"step_id":"1",'
                                '"content":"Move delegated test file","status":"pending","priority":"high"}]}}'
                            ),
                        },
                    },
                    {
                        "id": "tool_2",
                        "type": "function",
                        "function": {
                            "name": "delegate_tool",
                            "arguments": (
                                '{"worker_agent_id":"%s","task_prompt":"Use bash_tool to move the file %s to %s '
                                'and do not use code_tool for this move.","summary":"delegated file move"}'
                            )
                            % (worker_agent.agent_id, source_path.as_posix(), target_path.as_posix()),
                        },
                    },
                ],
                raw={"provider": "test"},
            ),
            LlmResponse(
                content="worker moved file",
                tool_calls=[
                    {
                        "id": "tool_3",
                        "type": "function",
                        "function": {
                            "name": "bash_tool",
                            "arguments": (
                                '{"command":"move \"%s\" \"%s\"","description":"Moves delegated test file"}'
                            )
                            % (str(source_path), str(target_path)),
                        },
                    }
                ],
                raw={"provider": "test"},
            ),
            LlmResponse(
                content="plan completed",
                tool_calls=[
                    {
                        "id": "tool_4",
                        "type": "function",
                        "function": {
                            "name": "plan_tool",
                            "arguments": (
                                '{"plan":{"title":"Move file","goal":"Move delegated test file",'
                                '"summary":"Delegated file moved","steps":[{"step_id":"1",'
                                '"content":"Move delegated test file","status":"completed","priority":"high"}]}}'
                            ),
                        },
                    }
                ],
                raw={"provider": "test"},
            ),
        ]
    )

    service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    monkeypatch.setattr(AgentExecutorFactory, "resolve", lambda self, runtime: executor)
    monkeypatch.setattr("app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    create_response = create_service.create_run(
        AgentRunCreateRequest(agent_id=orchestrator_agent.agent_id, workspace_id=uuid4(), metadata={})
    )

    response = service.input(
        create_response.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "plan, delegate, and move the test file with bash_tool"},
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    subtasks = list(STORE.subtasks.values())
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"
    assert len(subtasks) == 1

    worker_run = agent_run_repository.get_by_id(subtasks[0].worker_run_id)
    assert worker_run is not None
    assert worker_run.status == "completed"
    assert not source_path.exists()
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8").strip() == "test"

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status == "completed"

    assert [call["role"] for call in executor.calls] == ["orchestrator", "worker", "orchestrator"]
    assert executor.calls[0]["tools"] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert executor.calls[1]["tools"] == ["code_tool", "bash_tool"]
```

- [ ] **Step 2: Run the scripted delegate-chain test to verify it fails**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_delegate_chain_internal_bash_tool.py -v`
Expected: FAIL because orchestrator does not yet expose `bash_tool`, and the scripted move path has not been proven.

- [ ] **Step 3: Make the scripted test pass with the runtime changes already introduced**

No new production code should be required if Task 1 is complete. If the test still fails, only make the smallest required adjustments in the test fixture or command string to match Windows command behavior. Do not broaden `bash_tool` behavior beyond the test need.

- [ ] **Step 4: Run the scripted delegate-chain test to verify it passes**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_delegate_chain_internal_bash_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit the deterministic worker move coverage**

```bash
git add tests/test_delegate_chain_internal_bash_tool.py
git commit -m "test(runtime): add delegated bash tool chain coverage"
```

### Task 4: Add real internal LLM E2E coverage for orchestrator inspection and worker file moves

**Files:**
- Modify: `tests/test_delegate_chain_e2e_internal_llm.py`
- Test: `tests/test_delegate_chain_e2e_internal_llm.py`

- [ ] **Step 1: Write the failing real E2E tests**

Add two tests to `tests/test_delegate_chain_e2e_internal_llm.py`.

First test skeleton:

```python
def test_orchestrator_e2e_internal_llm_uses_bash_tool_before_plan(monkeypatch) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for real internal LLM test")

    repo_root = REPO_ROOT
    inspect_path = repo_root / ".AgentHub" / "tests" / "test1" / "bash_tool_test1.md"

    bootstrap_memory_store()

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": (
                    "Use only available runtime tools. Before creating a plan, inspect the file "
                    f"`{inspect_path.as_posix()}` with bash_tool. Do not assume its contents in plain text. "
                    "After inspection, create a one-step plan with plan_tool describing what you found."
                ),
            },
        )
    )

    trace: list[dict[str, object]] = []
    original_resolve = AgentExecutorFactory.resolve

    def recording_resolve(self, runtime):
        return RecordingExecutor(delegate=original_resolve(self, runtime), trace=trace)

    monkeypatch.setattr(AgentExecutorFactory, "resolve", recording_resolve)

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )

    create_response = create_service.create_run(
        AgentRunCreateRequest(agent_id=orchestrator_agent.agent_id, workspace_id=uuid4(), metadata={})
    )

    response = input_service.input(
        run_id=create_response.run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "Inspect the file with bash_tool and then create the plan."},
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    assert orchestrator_entries, trace
    assert "bash_tool" in orchestrator_entries[0]["visible_tools"]
    assert any("bash_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace
    assert any("plan_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status == "completed"
    assert Path(orchestrator_plan.file_path).exists()
```

Second test skeleton:

```python
def test_delegate_chain_e2e_internal_llm_uses_bash_tool_to_move_file(monkeypatch) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for real internal LLM test")

    source_path = REPO_ROOT / ".AgentHub" / "tests" / "test1" / "bash_tool_test1.md"
    target_path = REPO_ROOT / ".AgentHub" / "tests" / "test2" / "bash_tool_test1.md"

    bootstrap_memory_store()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("test\n", encoding="utf-8")

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()
    worker_agent = agent_repository.create(
        AgentModel(agent_id=uuid4(), agent_name="Internal Worker", agent_kind="worker")
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": (
                    "Run a real plan-delegate-callback flow using only the available runtime tools. "
                    "Create a one-step plan, delegate to the provided worker, and after callback complete the plan. "
                    f"The worker must move `{source_path.as_posix()}` to `{target_path.as_posix()}` using bash_tool. "
                    "Do not tell the worker to use code_tool for this move."
                ),
            },
        )
    )

    trace: list[dict[str, object]] = []
    original_resolve = AgentExecutorFactory.resolve

    def recording_resolve(self, runtime):
        return RecordingExecutor(delegate=original_resolve(self, runtime), trace=trace)

    monkeypatch.setattr(AgentExecutorFactory, "resolve", recording_resolve)
    monkeypatch.setattr("app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )

    create_response = create_service.create_run(
        AgentRunCreateRequest(agent_id=orchestrator_agent.agent_id, workspace_id=uuid4(), metadata={})
    )

    response = input_service.input(
        run_id=create_response.run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "Plan, delegate, move the file with bash_tool, and complete the plan."},
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"

    subtasks = list(STORE.subtasks.values())
    assert len(subtasks) == 1
    subtask = subtasks[0]
    assert subtask.status == "completed"

    worker_run = agent_run_repository.get_by_id(subtask.worker_run_id)
    assert worker_run is not None
    assert worker_run.status == "completed", worker_run.context_snapshot

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    worker_entries = [entry for entry in trace if entry["role"] == "worker"]
    assert worker_entries, trace
    assert "bash_tool" in worker_entries[0]["visible_tools"]
    assert worker_entries[0]["response_tool_calls"] == ["bash_tool"], worker_entries[0]["response_raw"]

    assert not source_path.exists()
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8").strip() == "test"

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status == "completed"
```

- [ ] **Step 2: Run the new real E2E tests to verify they fail or skip correctly**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_delegate_chain_e2e_internal_llm.py -v`
Expected:
- If provider env vars are missing: SKIPPED for the new tests
- If provider env vars are present: FAIL because orchestrator does not yet expose `bash_tool` and prompts are not yet aligned strongly enough

- [ ] **Step 3: Make the real E2E tests pass with the runtime and prompt changes already introduced**

Do not add new `bash_tool` features here. Only adjust the real test prompts or tiny runtime visibility details if the failures show prompt ambiguity or tool visibility mismatch.

- [ ] **Step 4: Run the full real E2E file to verify the suite passes or skips correctly**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_delegate_chain_e2e_internal_llm.py -v`
Expected:
- local environment without provider config: SKIPPED for real tests
- configured environment: PASS for the existing `code_tool` E2E and the two new `bash_tool` E2E tests

- [ ] **Step 5: Commit the real E2E coverage**

```bash
git add tests/test_delegate_chain_e2e_internal_llm.py
git commit -m "test(runtime): add bash tool e2e coverage"
```

### Task 5: Run full regression for the `bash_tool` E2E extension

**Files:**
- Modify: `tests/test_runtime_assembler.py`
- Modify: `tests/test_tool_resolver.py`
- Modify: `tests/test_prompt_composer.py`
- Create: `tests/test_delegate_chain_internal_bash_tool.py`
- Modify: `tests/test_delegate_chain_e2e_internal_llm.py`
- Test: `tests/test_runtime_assembler.py`
- Test: `tests/test_tool_resolver.py`
- Test: `tests/test_prompt_composer.py`
- Test: `tests/test_delegate_chain_internal_bash_tool.py`
- Test: `tests/test_delegate_chain_e2e_internal_llm.py`

- [ ] **Step 1: Run the targeted extension regression suite**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_assembler.py tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py -v`
Expected:
- pure runtime tests: PASS
- scripted delegate-chain test: PASS
- real E2E tests: PASS or SKIP depending on provider configuration

- [ ] **Step 2: Run the broader runtime regression suite**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_workspace_resolver.py tests/test_runtime_assembler.py tests/test_tool_call_handler.py tests/test_tool_resolver.py tests/test_runtime_policy_resolvers.py tests/test_code_tool.py tests/test_bash_tool.py tests/test_plan_tool.py tests/test_prompt_composer.py tests/test_agent_run_input_state_machine.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py -v`
Expected:
- runtime and tool regressions: PASS
- real internal LLM E2E tests: PASS or SKIP depending on provider configuration

- [ ] **Step 3: Commit any final test-alignment fixes discovered during regression**

```bash
git add tests/test_runtime_assembler.py tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py app/runtime/tools/tool_resolver.py app/runtime/prompt/mode/orchestrator_mode_prompt.py app/runtime/prompt/mode/worker_mode_prompt.py
git commit -m "test(runtime): verify bash tool e2e extension"
```
