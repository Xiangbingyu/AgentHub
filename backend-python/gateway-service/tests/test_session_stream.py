from fastapi.testclient import TestClient

from main import create_app


def test_session_stream_returns_text_event_stream(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.client.agent_service_client.AgentServiceClient.list_session_events",
        lambda self, session_id, after_sequence_no=None: [
            {
                "sequence_no": 1,
                "event_type": "session.message.appended",
                "payload": {"content": "hello"},
            }
        ],
    )

    client = TestClient(create_app())
    response = client.get("/sessions/00000000-0000-0000-0000-000000000001/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "session.message.appended" in response.text
