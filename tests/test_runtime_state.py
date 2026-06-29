from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.runtime_state import RuntimeStateStore


def test_default_state_uses_middle_school_policy(tmp_path):
    store = RuntimeStateStore(tmp_path / "state.json")

    state = store.read()

    assert state["studyStage"] == "middle"
    assert state["stageLabel"] == "初中"
    assert state["stageSource"] == "default"
    assert state["stageUpdatedAt"] == 0
    assert state["xiaozhiMcpUrl"] == ""
    assert state["xiaozhiMcpToken"] == ""
    assert state["awayTimeoutMinutes"] == 15
    assert state["policy"]["score_threshold"] == 65


def test_stage_is_persisted_with_source(tmp_path):
    path = tmp_path / "state.json"
    store = RuntimeStateStore(path)

    result = store.set_stage("高中", source="voice")
    reloaded = RuntimeStateStore(path).read()

    assert result["studyStage"] == "high"
    assert reloaded["studyStage"] == "high"
    assert reloaded["stageLabel"] == "高中"
    assert reloaded["stageSource"] == "voice"
    assert reloaded["stageUpdatedAt"] > 0
    assert reloaded["policy"]["persist_seconds"] == 25


def test_runtime_settings_are_merged_and_persisted(tmp_path):
    path = tmp_path / "state.json"
    store = RuntimeStateStore(path)

    result = store.update(
        {
            "awayTimeoutMinutes": 30,
            "xiaozhiMcpUrl": "wss://api.xiaozhi.me/mcp/example",
            "xiaozhiMcpToken": "secret-token",
        }
    )

    assert result["awayTimeoutMinutes"] == 30
    reloaded = RuntimeStateStore(path).read()
    assert reloaded["xiaozhiMcpUrl"].endswith("/example")
    assert reloaded["xiaozhiMcpToken"] == "secret-token"
    assert reloaded["studyStage"] == "middle"


def test_concurrent_updates_leave_complete_json(tmp_path):
    path = tmp_path / "state.json"
    store = RuntimeStateStore(path)

    def update(index: int) -> None:
        store.update({"awayTimeoutMinutes": index + 1})

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(update, range(20)))

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert 1 <= persisted["awayTimeoutMinutes"] <= 20
    assert persisted["studyStage"] == "middle"
    assert not list(tmp_path.glob("state.json.*.tmp"))


def test_store_creates_a_new_runtime_directory_before_locking(tmp_path):
    path = tmp_path / "new" / "runtime" / "state.json"
    store = RuntimeStateStore(path)

    assert store.read()["studyStage"] == "middle"
    store.set_stage("小学", "system")

    assert path.is_file()


@pytest.mark.parametrize("source", ["parent", "voice", "system"])
def test_stage_source_accepts_only_supported_enums(tmp_path, source):
    store = RuntimeStateStore(tmp_path / "state.json")

    result = store.set_stage("middle", source)

    assert result["stageSource"] == source
    assert store.read()["stageSource"] == source


def test_stage_source_rejects_sensitive_values_without_persisting_them(tmp_path):
    path = tmp_path / "state.json"
    store = RuntimeStateStore(path)
    sensitive_source = "wss://api.xiaozhi.me/mcp/full-secret-token"

    with pytest.raises(ValueError, match="^invalid_stage_source$") as error:
        store.set_stage("middle", sensitive_source)

    assert sensitive_source not in str(error.value)
    assert store.read()["stageSource"] == "default"
    if path.exists():
        assert sensitive_source not in path.read_text(encoding="utf-8")


def test_read_migrates_sensitive_legacy_stage_source(tmp_path):
    path = tmp_path / "state.json"
    sensitive_source = "wss://api.xiaozhi.me/mcp/legacy-secret-token"
    path.write_text(
        json.dumps(
            {
                "studyStage": "middle",
                "stageLabel": "初中",
                "stageSource": sensitive_source,
                "stageUpdatedAt": 123,
                "xiaozhiMcpUrl": "",
                "xiaozhiMcpToken": "",
                "awayTimeoutMinutes": 15,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = RuntimeStateStore(path).read()
    migrated = path.read_text(encoding="utf-8")

    assert state["stageSource"] == "system"
    assert sensitive_source not in repr(state)
    assert sensitive_source not in migrated


@pytest.mark.parametrize("corrupt_content", ["{not-json", "[]"])
def test_corrupt_runtime_state_is_quarantined_before_later_writes(
    tmp_path,
    corrupt_content,
):
    path = tmp_path / "state.json"
    path.write_text(corrupt_content, encoding="utf-8")
    store = RuntimeStateStore(path, clock=lambda: 123.456)

    state = store.read()

    backups = list(tmp_path.glob("state.json.corrupt-*"))
    assert state["studyStage"] == "middle"
    assert store.diagnostic_status["error"] in {
        "invalid_json",
        "invalid_structure",
    }
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == corrupt_content
    assert not path.exists()

    store.update({"awayTimeoutMinutes": 20})

    assert json.loads(path.read_text(encoding="utf-8"))["awayTimeoutMinutes"] == 20
    assert backups[0].read_text(encoding="utf-8") == corrupt_content
