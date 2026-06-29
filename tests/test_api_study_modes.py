from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main
from backend.engine import EngineConfig, FocusEngine
from backend.reminder_policy import ReminderPolicy
from backend.runtime_state import RuntimeStateStore
from backend.xiaozhi_bridge import ReminderStore
from backend.xiaozhi_mcp_runtime import XiaozhiMcpRuntime


class FakeProcess:
    def __init__(self):
        self.pid = 7070
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


def make_client(tmp_path, monkeypatch):
    (tmp_path / "mcp_pipe.py").write_text("", encoding="utf-8")
    (tmp_path / "focus_reminder_mcp.py").write_text("", encoding="utf-8")
    state_store = RuntimeStateStore(tmp_path / "runtime_state.json")
    reminder_store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=state_store,
    )
    engine = FocusEngine(
        EngineConfig(mock_mode=True),
        state_store=state_store,
        reminder_store=reminder_store,
        reminder_policy=ReminderPolicy(),
    )
    process = FakeProcess()
    runtime = XiaozhiMcpRuntime(
        state_store=state_store,
        runtime_dir=tmp_path / "mcp-runtime",
        process_factory=lambda *args, **kwargs: process,
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "state_store", state_store)
    monkeypatch.setattr(main, "reminder_store", reminder_store)
    monkeypatch.setattr(main, "mcp_runtime", runtime)
    return TestClient(main.app), state_store, reminder_store


def test_settings_support_v2_fields_and_never_return_complete_token(
    tmp_path,
    monkeypatch,
):
    client, state_store, _ = make_client(tmp_path, monkeypatch)

    default = client.get("/settings")
    assert default.status_code == 200
    assert default.json()["ageMode"] == "middle"
    assert default.json()["studyStage"] == "middle"

    response = client.post(
        "/settings",
        json={
            "awayTimeoutMinutes": 22,
            "xiaozhiMcpUrl": "wss://api.xiaozhi.me/mcp/",
            "xiaozhiMcpToken": "complete-secret-token",
            "ageMode": "primary",
            "stageSource": "parent",
        },
    )

    assert response.status_code == 200
    assert response.json()["studyStage"] == "primary"
    assert "complete-secret-token" not in response.text
    persisted = state_store.read()
    assert persisted["xiaozhiMcpToken"] == "complete-secret-token"
    assert persisted["awayTimeoutMinutes"] == 22


def test_study_stage_endpoints_share_runtime_state(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)

    changed = client.post(
        "/study-stage",
        json={"stage": "high", "source": "voice"},
    )
    current = client.get("/study-stage")

    assert changed.status_code == 200
    assert changed.json()["stageLabel"] == "高中"
    assert current.json()["studyStage"] == "high"
    assert current.json()["stageSource"] == "voice"


def test_mcp_config_rejects_noncanonical_endpoint_and_redacts_status(
    tmp_path,
    monkeypatch,
):
    client, _, _ = make_client(tmp_path, monkeypatch)

    rejected = client.post(
        "/mcp/config",
        json={"endpoint": "wss://evil.example/mcp/token"},
    )
    assert rejected.status_code == 400

    configured = client.post(
        "/mcp/config",
        json={"endpoint": "wss://api.xiaozhi.me/mcp/secret-token"},
    )
    started = client.post("/mcp/start")
    status = client.get("/mcp/status")
    stopped = client.post("/mcp/stop")

    assert configured.status_code == 200
    assert started.json()["running"] is True
    assert "secret-token" not in status.text
    assert stopped.json()["stopped"] is True


def test_control_enqueues_only_reminder_commands(tmp_path, monkeypatch):
    client, _, reminder_store = make_client(tmp_path, monkeypatch)

    assert client.post(
        "/control",
        json={"command": "parent_message", "text": "家长提醒"},
    ).status_code == 200
    assert client.post(
        "/control",
        json={"command": "ai_script_message", "text": "AI 提醒"},
    ).status_code == 200
    assert client.post(
        "/control",
        json={"command": "refresh_stream"},
    ).status_code == 200

    snapshot = reminder_store.snapshot()
    assert snapshot["pendingCount"] == 2
    assert [item["command"] for item in snapshot["items"]] == [
        "parent_message",
        "ai_script_message",
    ]


def test_existing_health_state_sources_and_snapshot_still_work(
    tmp_path,
    monkeypatch,
):
    client, _, _ = make_client(tmp_path, monkeypatch)

    assert client.get("/health").json()["ok"] is True
    state = client.get("/state")
    assert state.status_code == 200
    assert state.json()["studyStage"] == "middle"
    assert client.get("/sources").status_code == 200
    snapshot = client.get("/snapshot.jpg")
    assert snapshot.status_code == 200
    assert snapshot.headers["content-type"] == "image/jpeg"


def test_settings_round_trip_preserves_a_long_masked_token(
    tmp_path,
    monkeypatch,
):
    client, state_store, _ = make_client(tmp_path, monkeypatch)
    token = "complete-secret-token"
    payload = {
        "awayTimeoutMinutes": 15,
        "xiaozhiMcpUrl": "wss://api.xiaozhi.me/mcp/",
        "xiaozhiMcpToken": token,
        "ageMode": "middle",
        "stageSource": "parent",
    }
    assert client.post("/settings", json=payload).status_code == 200
    public_settings = client.get("/settings").json()

    response = client.post("/settings", json=public_settings)

    assert response.status_code == 200
    assert state_store.read()["xiaozhiMcpToken"] == token


def test_shutdown_stops_engine_and_owned_mcp_runtime(monkeypatch):
    calls = []

    class Service:
        def stop(self):
            calls.append(self)

    engine = Service()
    runtime = Service()
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "mcp_runtime", runtime)

    main.on_shutdown()

    assert calls == [runtime, engine]
