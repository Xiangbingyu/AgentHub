import json

from fastapi.testclient import TestClient

import gateway_service.app.api.session_stream as session_stream
from gateway_service.app.main import create_app


def _fast_polling(monkeypatch) -> None:
    # 让轮询间隔趋零、空轮 2 次即收尾，保证测试快速且确定性终止
    monkeypatch.setattr(session_stream, "STREAM_ACTIVE_INTERVAL", 0.0)
    monkeypatch.setattr(session_stream, "STREAM_IDLE_INTERVAL", 0.0)
    monkeypatch.setattr(session_stream, "STREAM_MAX_IDLE_POLLS", 2)


def test_session_stream_serializes_payload_as_json(monkeypatch) -> None:
    _fast_polling(monkeypatch)
    monkeypatch.setattr(
        "gateway_service.app.client.agent_service_client.AgentServiceClient.list_session_events",
        lambda self, session_id, since=0: (
            [
                {
                    "sequence_no": 5,
                    "event_type": "session.message.appended",
                    "payload": {"content": "你好", "role": "assistant"},
                }
            ]
            if since < 5
            else []
        ),
    )

    client = TestClient(create_app())
    response = client.get("/sessions/sid-1/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    text = response.text

    assert "id: 5" in text
    assert "event: session.message.appended" in text
    data_line = next(
        line[len("data: "):] for line in text.splitlines() if line.startswith("data: ")
    )
    parsed = json.loads(data_line)
    assert parsed == {"content": "你好", "role": "assistant"}


def test_session_stream_respects_last_event_id(monkeypatch) -> None:
    _fast_polling(monkeypatch)
    seen = {}

    def _fake(self, session_id, since=0):
        seen["since"] = since
        return []

    monkeypatch.setattr(
        "gateway_service.app.client.agent_service_client.AgentServiceClient.list_session_events",
        _fake,
    )

    client = TestClient(create_app())
    response = client.get("/sessions/sid-1/stream", headers={"Last-Event-ID": "7"})

    assert response.status_code == 200
    _ = response.text
    assert seen["since"] == 7
