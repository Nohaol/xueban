from fastapi.testclient import TestClient

from backend.main import app


def test_local_agent_page_is_available() -> None:
    with TestClient(app) as client:
        response = client.get("/local-agent")

    assert response.status_code == 200
    assert "本地智能体运行中心" in response.text
    assert "/static/local-agent.js" in response.text


def test_local_agent_status_endpoint_has_expected_sections() -> None:
    with TestClient(app) as client:
        response = client.get("/local-agent/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert {"device", "stage", "network", "services", "reminders"} <= payload.keys()
