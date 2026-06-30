from __future__ import annotations

import io
import json

from backend.active_speech import ActiveSpeechClient, ActiveSpeechDispatcher
from backend.runtime_state import RuntimeStateStore
from backend.xiaozhi_bridge import ReminderStore


class ImmediateExecutor:
    def submit(self, function, *args, **kwargs):
        function(*args, **kwargs)

    def shutdown(self, wait=False):
        return None


class FakeResponse:
    def __init__(self, status=202, payload=None):
        self.status = status
        self._body = json.dumps(payload or {"ok": True}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self._body


def make_store(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    return ReminderStore(tmp_path / "reminders.json", state_store=state)


def test_client_posts_study_alert_to_configured_device():
    captured = {}

    def opener(request, *, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            payload={"ok": True, "status": "sent", "request_id": "reminder-1"}
        )

    client = ActiveSpeechClient(
        "http://127.0.0.1:18007/study-alert",
        "90:70:69:0e:a4:ac",
        opener=opener,
    )

    result = client.send(
        {
            "id": "reminder-1",
            "text": "请把注意力放回题目。",
        }
    )

    assert result["accepted"] is True
    assert captured["url"] == "http://127.0.0.1:18007/study-alert"
    assert captured["timeout"] == 2.0
    assert captured["payload"] == {
        "device_id": "90:70:69:0e:a4:ac",
        "request_id": "reminder-1",
        "text": "请把注意力放回题目。",
        "status": "学习提醒",
        "emotion": "neutral",
        "interrupt": True,
    }


def test_dispatcher_completes_queue_only_after_gateway_accepts(tmp_path):
    store = make_store(tmp_path)
    reminder = store.enqueue("managed_ai_reminder", "继续专注。")

    class AcceptingClient:
        enabled = True

        def send(self, item):
            return {"accepted": True, "status": "sent"}

    dispatcher = ActiveSpeechDispatcher(
        AcceptingClient(),
        store,
        executor=ImmediateExecutor(),
    )

    assert dispatcher.dispatch(reminder) is True
    queued = store.snapshot()["items"][0]
    assert queued["status"] == "spoken"
    assert queued["delivery"] == "active_speech"


def test_dispatcher_keeps_pending_reminder_when_device_is_offline(tmp_path):
    store = make_store(tmp_path)
    reminder = store.enqueue("managed_ai_reminder", "继续专注。")

    class OfflineClient:
        enabled = True

        def send(self, item):
            return {
                "accepted": False,
                "status": "device_offline",
                "error": "device_offline",
            }

    dispatcher = ActiveSpeechDispatcher(
        OfflineClient(),
        store,
        executor=ImmediateExecutor(),
    )

    assert dispatcher.dispatch(reminder) is True
    assert store.snapshot()["items"][0]["status"] == "pending"
    assert dispatcher.status()["lastError"] == "device_offline"


def test_disabled_client_does_not_claim_mcp_fallback(tmp_path):
    store = make_store(tmp_path)
    reminder = store.enqueue("parent_message", "再坚持十分钟。")
    dispatcher = ActiveSpeechDispatcher(
        ActiveSpeechClient("", ""),
        store,
        executor=ImmediateExecutor(),
    )

    assert dispatcher.dispatch(reminder) is False
    assert store.snapshot()["pendingCount"] == 1
