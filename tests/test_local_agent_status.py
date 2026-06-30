from pathlib import Path

from backend.local_agent_status import (
    build_local_agent_status,
    extract_firmware_target,
)


def test_extract_firmware_target_reads_ota_url(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        '{"CONFIG_OTA_URL": "http://10.1.2.3:18003/a"}',
        encoding="utf-8",
    )

    assert extract_firmware_target(config) == {
        "url": "http://10.1.2.3:18003/a",
        "host": "10.1.2.3",
        "port": 18003,
    }


def test_extract_firmware_target_reads_sdkconfig_append(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        '{"builds":[{"sdkconfig_append":['
        '"CONFIG_OTA_URL=\\\"http://10.9.8.7:18003/a\\\""'
        "]}]}",
        encoding="utf-8",
    )

    assert extract_firmware_target(config)["host"] == "10.9.8.7"


def test_build_local_agent_status_is_safe_and_summarizes_runtime() -> None:
    state = {
        "studyStage": "high",
        "stageLabel": "高中",
        "stageSource": "voice",
        "xiaozhiMcpToken": "must-not-leak",
    }
    reminders = {
        "pendingCount": 1,
        "completedCount": 2,
        "items": [
            {
                "id": "abc123",
                "command": "parent_message",
                "text": "再坚持十分钟",
                "status": "spoken",
                "delivery": "active_speech",
                "createdAt": 100,
            }
        ],
    }

    payload = build_local_agent_status(
        state=state,
        reminders=reminders,
        active_speech={
            "enabled": True,
            "lastStatus": "sent",
            "lastError": None,
        },
        current_ip="10.1.2.3",
        firmware_target={
            "url": "http://10.1.2.3:18003/a",
            "host": "10.1.2.3",
            "port": 18003,
        },
        service_probe=lambda port: port != 18007,
        now_ms=200,
    )

    assert payload["ok"] is True
    assert payload["stage"]["key"] == "high"
    assert payload["network"]["targetMatchesCurrent"] is True
    assert payload["services"][0]["port"] == 8000
    assert payload["services"][-1]["online"] is False
    assert payload["reminders"]["recent"][0]["text"] == "再坚持十分钟"
    assert "must-not-leak" not in repr(payload)
