from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.runtime_state import RuntimeStateStore
from backend.xiaozhi_bridge import ReminderStore


def test_voice_stage_sync_and_stage_metadata(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    reminders = ReminderStore(tmp_path / "reminders.json", state_store=state)

    stage = state.set_stage("高中", "voice")
    item = reminders.enqueue(
        "managed_ai_reminder",
        "回到当前目标。",
        {"focusScore": 42},
    )

    assert stage["studyStage"] == "high"
    assert item["studyStage"] == "high"
    assert item["stageLabel"] == "高中"
    assert item["policyVersion"] == "stage-v1"
    assert item["focusPayload"]["focusScore"] == 42
    assert item["status"] == "pending"


def test_pop_is_atomic_and_acknowledges_delivered_item(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    path = tmp_path / "reminders.json"
    first_store = ReminderStore(path, state_store=state)
    second_store = ReminderStore(path, state_store=state)
    queued = first_store.enqueue("parent_message", "先完成这一题。")

    popped = second_store.pop_next()

    assert popped["hasReminder"] is True
    assert popped["reminderId"] == queued["id"]
    assert popped["reminderText"] == "先完成这一题。"
    assert first_store.pop_next() == {"hasReminder": False}

    acknowledged = first_store.acknowledge(queued["id"], spoken=True)
    assert acknowledged["acknowledged"] is True
    assert acknowledged["item"]["status"] == "spoken"
    assert acknowledged["item"]["acknowledgedAt"] > 0


def test_acknowledge_unknown_reminder_is_explicit(tmp_path):
    store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=RuntimeStateStore(tmp_path / "state.json"),
    )

    assert store.acknowledge("missing") == {
        "success": False,
        "acknowledged": False,
        "error": "reminder_not_found",
    }


def test_snapshot_reports_queue_counts_without_consuming(tmp_path):
    store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=RuntimeStateStore(tmp_path / "state.json"),
    )
    store.enqueue("managed_ai_reminder", "提醒一")
    store.enqueue("managed_ai_reminder", "提醒二")

    snapshot = store.snapshot()

    assert snapshot["pendingCount"] == 2
    assert snapshot["deliveredCount"] == 0
    assert len(snapshot["items"]) == 2
    assert store.pop_next()["hasReminder"] is True


def test_concurrent_pops_do_not_deliver_the_same_item_twice(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    path = tmp_path / "reminders.json"
    writer = ReminderStore(path, state_store=state)
    for index in range(5):
        writer.enqueue("managed_ai_reminder", f"提醒 {index}")

    def pop_once() -> dict:
        return ReminderStore(path, state_store=state).pop_next()

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: pop_once(), range(5)))

    reminder_ids = [result["reminderId"] for result in results]
    assert len(set(reminder_ids)) == 5


def test_reminder_store_creates_a_new_runtime_directory_before_locking(tmp_path):
    runtime_dir = tmp_path / "new" / "runtime"
    state = RuntimeStateStore(runtime_dir / "state.json")
    reminders = ReminderStore(
        runtime_dir / "reminders.json",
        state_store=state,
    )

    item = reminders.enqueue("parent_message", "继续完成当前任务。")

    assert item["status"] == "pending"
    assert (runtime_dir / "reminders.json").is_file()


def test_pending_reminder_cannot_be_acknowledged(tmp_path):
    store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=RuntimeStateStore(tmp_path / "state.json"),
    )
    queued = store.enqueue("parent_message", "继续完成当前任务。")

    result = store.acknowledge(queued["id"], spoken=True)

    assert result == {
        "success": False,
        "acknowledged": False,
        "error": "invalid_reminder_state",
    }
    assert store.snapshot()["items"][0]["status"] == "pending"


def test_delivered_reminder_can_be_skipped(tmp_path):
    store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=RuntimeStateStore(tmp_path / "state.json"),
    )
    queued = store.enqueue("managed_ai_reminder", "提醒")
    store.pop_next()

    result = store.acknowledge(queued["id"], spoken=False)

    assert result["success"] is True
    assert result["item"]["status"] == "skipped"
    assert result["item"]["spoken"] is False


def test_terminal_acknowledgement_is_idempotent(tmp_path):
    now = [100.0]
    store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=RuntimeStateStore(tmp_path / "state.json"),
        clock=lambda: now[0],
    )
    queued = store.enqueue("managed_ai_reminder", "提醒")
    store.pop_next()
    first = store.acknowledge(queued["id"], spoken=True)
    now[0] = 200.0

    repeated = store.acknowledge(queued["id"], spoken=False)

    assert repeated["success"] is True
    assert repeated["idempotent"] is True
    assert repeated["item"]["status"] == "spoken"
    assert repeated["item"]["spoken"] is True
    assert repeated["item"]["acknowledgedAt"] == first["item"]["acknowledgedAt"]


def test_expired_delivery_lease_is_reclaimed(tmp_path):
    now = [100.0]
    store = ReminderStore(
        tmp_path / "reminders.json",
        state_store=RuntimeStateStore(tmp_path / "state.json"),
        clock=lambda: now[0],
        lease_seconds=30,
    )
    queued = store.enqueue("managed_ai_reminder", "提醒")

    first = store.pop_next()
    assert first["reminderId"] == queued["id"]
    assert first["leaseExpiresAt"] == 130000
    assert store.pop_next() == {"hasReminder": False}

    now[0] = 131.0
    reclaimed = store.pop_next()

    assert reclaimed["reminderId"] == queued["id"]
    assert reclaimed["deliveredAt"] == 131000
    assert reclaimed["leaseExpiresAt"] == 161000


@pytest.mark.parametrize(
    "corrupt_payload",
    [
        "{not-json",
        json.dumps([]),
        json.dumps({"version": 1, "items": "not-a-list"}),
        json.dumps({"version": 1, "items": [{"id": "valid"}, "not-an-object"]}),
    ],
)
def test_corrupt_reminder_queue_is_quarantined_before_later_writes(
    tmp_path,
    corrupt_payload,
):
    path = tmp_path / "reminders.json"
    path.write_text(corrupt_payload, encoding="utf-8")
    state = RuntimeStateStore(tmp_path / "state.json")
    store = ReminderStore(
        path,
        state_store=state,
        clock=lambda: 123.456,
    )

    snapshot = store.snapshot()

    backups = list(tmp_path.glob("reminders.json.corrupt-*"))
    assert snapshot["items"] == []
    assert store.diagnostic_status["error"] in {
        "invalid_json",
        "invalid_structure",
    }
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == corrupt_payload
    assert not path.exists()

    store.enqueue("managed_ai_reminder", "continue")

    assert len(json.loads(path.read_text(encoding="utf-8"))["items"]) == 1
    assert backups[0].read_text(encoding="utf-8") == corrupt_payload
