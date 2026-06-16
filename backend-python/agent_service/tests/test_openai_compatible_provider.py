import threading
import time
from types import SimpleNamespace

from agent_service.app.llm.llm_types import LlmMessage, LlmRequest
from agent_service.app.llm.openai_compatible_provider import OpenAICompatibleProvider


def test_openai_compatible_provider_returns_tool_calls(monkeypatch) -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
    )

    payload = {
        "choices": [
            {
                "message": {
                    "content": "I'll use a tool now.",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "code_tool",
                                "arguments": '{"action":"write_file","path":"demo.py","content":"print(1)"}',
                            },
                        }
                    ],
                }
            }
        ]
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    class FakeClient:
        def post(self, *args, **kwargs):
            return FakeResponse()

        def close(self):
            return None

    monkeypatch.setattr(
        "agent_service.app.llm.openai_compatible_provider.httpx.Client",
        lambda: FakeClient(),
    )

    response = provider.complete(
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[],
            tools=[{"type": "function", "function": {"name": "code_tool", "parameters": {}}}],
            tool_choice="auto",
        )
    )

    assert response.content == "I'll use a tool now."
    assert response.tool_calls == payload["choices"][0]["message"]["tool_calls"]


def test_openai_compatible_provider_preserves_tool_message_fields(monkeypatch) -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": "done", "tool_calls": []}}]}

    class FakeClient:
        def post(self, *args, **kwargs):
            captured["payload"] = kwargs["content"]
            return FakeResponse()

        def close(self):
            return None

    monkeypatch.setattr(
        "agent_service.app.llm.openai_compatible_provider.httpx.Client",
        lambda: FakeClient(),
    )

    provider.complete(
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[
                LlmMessage(
                    role="assistant",
                    content="I'll use a tool now.",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "bash_tool", "arguments": '{"command":"echo hi"}'},
                        }
                    ],
                ),
                LlmMessage(
                    role="tool",
                    content='{"ok": true}',
                    tool_call_id="call_1",
                ),
            ],
            tools=[{"type": "function", "function": {"name": "bash_tool", "parameters": {}}}],
            tool_choice="auto",
        )
    )

    assert '"tool_calls": [{"id": "call_1"' in captured["payload"]
    assert '"tool_call_id": "call_1"' in captured["payload"]


def test_openai_compatible_provider_can_be_interrupted(monkeypatch) -> None:
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
    )
    cancel_event = threading.Event()
    started = threading.Event()
    closed = threading.Event()

    class FakeClient:
        def post(self, *args, **kwargs):
            started.set()
            while not closed.is_set():
                time.sleep(0.05)
            raise RuntimeError("request aborted")

        def close(self):
            closed.set()

    monkeypatch.setattr(
        "agent_service.app.llm.openai_compatible_provider.httpx.Client",
        lambda: FakeClient(),
    )

    def _run():
        try:
            provider.complete(
                LlmRequest(
                    system_prompt="system",
                    context_prompt="context",
                    messages=[LlmMessage(role="user", content="hello")],
                ),
                cancel_event=cancel_event,
            )
        except RuntimeError as exc:
            assert str(exc) == "request aborted"

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    assert started.wait(timeout=1)

    cancel_event.set()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert closed.is_set()

