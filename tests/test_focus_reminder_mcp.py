from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def load_bridge_module(monkeypatch, tmp_path):
    monkeypatch.setenv("XUEBAN_RUNTIME_DIR", str(tmp_path))
    script = (
        Path(__file__).resolve().parents[1]
        / "xiaozhi_bridge"
        / "focus_reminder_mcp.py"
    )
    spec = importlib.util.spec_from_file_location("focus_reminder_mcp_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mcp_tools_share_stage_and_reminder_state(monkeypatch, tmp_path):
    bridge = load_bridge_module(monkeypatch, tmp_path)

    stage = bridge.set_study_stage("小学", "voice")
    queued = bridge.reminder_store.enqueue("managed_ai_reminder", "完成这一小步。")
    popped = bridge.check_study_focus_and_remind_child()
    acknowledged = bridge.mark_study_reminder_spoken(
        popped["reminderId"],
        spoken=True,
    )
    inspected = bridge.inspect_study_reminder_queue()

    assert stage["studyStage"] == "primary"
    assert bridge.get_study_stage()["stageLabel"] == "小学"
    assert queued["studyStage"] == "primary"
    assert popped["hasReminder"] is True
    assert acknowledged["item"]["status"] == "spoken"
    assert inspected["completedCount"] == 1


def test_mcp_check_returns_explicit_empty_result(monkeypatch, tmp_path):
    bridge = load_bridge_module(monkeypatch, tmp_path)

    assert bridge.check_study_focus_and_remind_child() == {
        "hasReminder": False
    }


def test_mcp_stage_tools_return_only_safe_stage_fields(monkeypatch, tmp_path):
    bridge = load_bridge_module(monkeypatch, tmp_path)
    bridge.state_store.update(
        {
            "xiaozhiMcpUrl": "wss://api.xiaozhi.me/mcp/",
            "xiaozhiMcpToken": "do-not-return-this-token",
            "awayTimeoutMinutes": 30,
        }
    )

    changed = bridge.set_study_stage("高中", "voice")
    current = bridge.get_study_stage()

    expected_fields = {
        "studyStage",
        "stageLabel",
        "stageSource",
        "stageUpdatedAt",
        "policy",
    }
    assert set(changed) == expected_fields
    assert set(current) == expected_fields
    assert "do-not-return-this-token" not in repr(changed)
    assert "do-not-return-this-token" not in repr(current)
    assert "wss://api.xiaozhi.me/mcp/" not in repr(changed)
    assert "wss://api.xiaozhi.me/mcp/" not in repr(current)


def test_every_mcp_tool_writes_a_credential_free_jsonl_call_log(
    monkeypatch,
    tmp_path,
):
    bridge = load_bridge_module(monkeypatch, tmp_path)
    token = "never-log-this-token"
    endpoint = "wss://api.xiaozhi.me/mcp/"
    bridge.state_store.update(
        {
            "xiaozhiMcpUrl": endpoint,
            "xiaozhiMcpToken": token,
        }
    )

    bridge.set_study_stage("小学", "voice")
    bridge.get_study_stage()
    bridge.reminder_store.enqueue("managed_ai_reminder", "完成这一小步。")
    pulled = bridge.check_study_focus_and_remind_child()
    bridge.mark_study_reminder_spoken(pulled["reminderId"], spoken=True)
    bridge.inspect_study_reminder_queue()

    log_path = tmp_path / "xiaozhi_mcp_calls.jsonl"
    raw_log = log_path.read_text(encoding="utf-8")
    records = [json.loads(line) for line in raw_log.splitlines()]

    assert [record["tool"] for record in records] == [
        "set_study_stage",
        "get_study_stage",
        "check_study_focus_and_remind_child",
        "mark_study_reminder_spoken",
        "inspect_study_reminder_queue",
    ]
    assert token not in raw_log
    assert endpoint not in raw_log
    assert records[0]["request"] == {"stage": "primary", "source": "voice"}
    assert set(records[0]["result"]) == {
        "studyStage",
        "stageLabel",
        "stageSource",
        "stageUpdatedAt",
        "policy",
    }


def test_invalid_sensitive_stage_inputs_are_not_returned_persisted_or_logged(
    monkeypatch,
    tmp_path,
):
    bridge = load_bridge_module(monkeypatch, tmp_path)
    sensitive_source = "wss://api.xiaozhi.me/mcp/source-secret-token"
    sensitive_stage = "invalid-stage-with-secret-token"

    with pytest.raises(ValueError, match="^invalid_stage_source$") as source_error:
        bridge.set_study_stage("middle", sensitive_source)
    with pytest.raises(ValueError, match="^invalid_study_stage$") as stage_error:
        bridge.set_study_stage(sensitive_stage, "voice")

    persisted = bridge.state_store.read()
    raw_log = bridge.CALL_LOG_PATH.read_text(encoding="utf-8")
    records = [json.loads(line) for line in raw_log.splitlines()]

    assert sensitive_source not in str(source_error.value)
    assert sensitive_stage not in str(stage_error.value)
    assert sensitive_source not in repr(persisted)
    assert sensitive_stage not in repr(persisted)
    assert sensitive_source not in raw_log
    assert sensitive_stage not in raw_log
    assert records == [
        {
            "timestamp": records[0]["timestamp"],
            "tool": "set_study_stage",
            "request": {},
            "result": {"success": False, "error": "invalid_stage_source"},
        },
        {
            "timestamp": records[1]["timestamp"],
            "tool": "set_study_stage",
            "request": {},
            "result": {"success": False, "error": "invalid_study_stage"},
        },
    ]


def test_mcp_get_migrates_sensitive_legacy_stage_source_without_leaking(
    monkeypatch,
    tmp_path,
):
    sensitive_source = "wss://api.xiaozhi.me/mcp/legacy-mcp-secret-token"
    state_path = tmp_path / "runtime_state.json"
    state_path.write_text(
        json.dumps(
            {
                "studyStage": "high",
                "stageLabel": "高中",
                "stageSource": sensitive_source,
                "stageUpdatedAt": 456,
                "xiaozhiMcpUrl": "",
                "xiaozhiMcpToken": "",
                "awayTimeoutMinutes": 15,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bridge = load_bridge_module(monkeypatch, tmp_path)

    response = bridge.get_study_stage()
    raw_log = bridge.CALL_LOG_PATH.read_text(encoding="utf-8")
    migrated = state_path.read_text(encoding="utf-8")

    assert response["stageSource"] == "system"
    assert sensitive_source not in repr(response)
    assert sensitive_source not in raw_log
    assert sensitive_source not in migrated


def test_audit_log_failure_does_not_fail_tool_or_lose_reminder(
    monkeypatch,
    tmp_path,
):
    bridge = load_bridge_module(monkeypatch, tmp_path)
    queued = bridge.reminder_store.enqueue(
        "managed_ai_reminder",
        "完成当前任务。",
    )

    def fail_log(*args, **kwargs):
        raise OSError("audit disk unavailable")

    monkeypatch.setattr(bridge, "_write_call_log", fail_log)

    result = bridge.check_study_focus_and_remind_child()

    assert result["hasReminder"] is True
    assert result["reminderId"] == queued["id"]
    assert result["leaseExpiresAt"] > result["deliveredAt"]
