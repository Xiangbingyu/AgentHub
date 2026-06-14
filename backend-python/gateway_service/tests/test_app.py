from fastapi.testclient import TestClient

from gateway_service.main import create_app


def test_gateway_package_exposes_create_app_from_app_main() -> None:
    from gateway_service.app.main import create_app as app_create_app

    assert create_app is app_create_app


def test_gateway_app_healthz() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
