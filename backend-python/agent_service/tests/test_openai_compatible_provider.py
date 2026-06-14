from types import SimpleNamespace

from agent_service.app.llm.llm_types import LlmRequest
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

    monkeypatch.setattr("agent_service.app.llm.openai_compatible_provider.httpx.post", lambda *args, **kwargs: FakeResponse())

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
