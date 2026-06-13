from fastapi.testclient import TestClient

from main import create_app


def test_gateway_app_healthz() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
