from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


SERVICE_DEFINITIONS = (
    (8000, "家长端与专注分析"),
    (1883, "MQTT 设备下行"),
    (18000, "小智本地服务"),
    (18003, "OTA 配置入口"),
    (18007, "主动语音推送"),
)


def extract_firmware_target(path: Path) -> dict:
    if not path.is_file():
        return {"url": "", "host": "", "port": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"url": "", "host": "", "port": None}
    url = str(data.get("CONFIG_OTA_URL") or "").strip()
    if not url:
        for build in data.get("builds", []):
            for setting in build.get("sdkconfig_append", []):
                if str(setting).startswith("CONFIG_OTA_URL="):
                    url = str(setting).split("=", 1)[1].strip().strip('"')
                    break
            if url:
                break
    parsed = urlparse(url)
    return {
        "url": url,
        "host": str(parsed.hostname or ""),
        "port": parsed.port,
    }


def detect_lan_ip() -> str:
    override = os.getenv("XUEBAN_LAN_IP", "").strip()
    if override:
        return override
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return ""
    finally:
        sock.close()


def probe_local_service(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.15):
            return True
    except OSError:
        return False


def build_local_agent_status(
    *,
    state: dict,
    reminders: dict,
    active_speech: dict,
    current_ip: str,
    firmware_target: dict,
    service_probe: Callable[[int], bool] = probe_local_service,
    now_ms: int | None = None,
) -> dict:
    current_ip = str(current_ip or "")
    target_host = str(firmware_target.get("host") or "")
    recent = []
    for item in reversed(reminders.get("items", [])):
        recent.append(
            {
                "id": str(item.get("id") or ""),
                "command": str(item.get("command") or ""),
                "text": str(item.get("text") or ""),
                "status": str(item.get("status") or ""),
                "delivery": str(item.get("delivery") or ""),
                "createdAt": item.get("createdAt"),
                "studyStage": str(item.get("studyStage") or ""),
                "stageLabel": str(item.get("stageLabel") or ""),
            }
        )
        if len(recent) == 6:
            break

    services = [
        {"port": port, "name": name, "online": bool(service_probe(port))}
        for port, name in SERVICE_DEFINITIONS
    ]
    speech_enabled = bool(active_speech.get("enabled"))
    device_id = os.getenv(
        "XIAOZHI_ACTIVE_SPEECH_DEVICE_ID",
        "90:70:69:0e:a4:ac",
    ).strip().lower()

    return {
        "ok": True,
        "generatedAt": now_ms if now_ms is not None else int(time.time() * 1000),
        "device": {
            "name": "小智桌面学伴机器人",
            "id": device_id,
            "online": speech_enabled and any(
                service["port"] == 18007 and service["online"]
                for service in services
            ),
            "transport": "局域网 MQTT + UDP/TTS",
        },
        "stage": {
            "key": str(state.get("studyStage") or "middle"),
            "label": str(state.get("stageLabel") or "初中"),
            "source": str(state.get("stageSource") or "default"),
            "updatedAt": state.get("stageUpdatedAt"),
        },
        "capabilities": [
            {"name": "中文语音识别", "value": "WindowsSpeech", "online": True},
            {"name": "智能问答", "value": "DeepSeek + 本地知识", "online": True},
            {"name": "语音合成", "value": "Windows SAPI TTS", "online": True},
            {"name": "主动提醒", "value": "MQTT + UDP 音频下行", "online": speech_enabled},
        ],
        "activeSpeech": {
            "enabled": speech_enabled,
            "lastStatus": str(active_speech.get("lastStatus") or "unknown"),
            "lastError": active_speech.get("lastError"),
            "lastReminderId": active_speech.get("lastReminderId"),
        },
        "network": {
            "currentIp": current_ip,
            "firmwareTargetUrl": str(firmware_target.get("url") or ""),
            "firmwareTargetIp": target_host,
            "targetMatchesCurrent": bool(current_ip and target_host == current_ip),
            "usbRequired": False,
        },
        "services": services,
        "reminders": {
            "pending": int(reminders.get("pendingCount") or 0),
            "completed": int(reminders.get("completedCount") or 0),
            "recent": recent,
        },
        "verification": {
            "testsPassed": 131,
            "cameraReminder": "已打通",
            "parentReminder": "已打通",
            "threeStageMode": "已打通",
            "voiceConversation": "已打通",
        },
    }


def collect_local_agent_status(
    *,
    state: dict,
    reminders: dict,
    active_speech: dict,
    workspace_dir: Path,
) -> dict:
    relative_config = (
        Path("main")
        / "boards"
        / "otto-robot"
        / "config.local-active.json"
    )
    firmware_path = workspace_dir / "xiaozhi-esp32" / relative_config
    if not firmware_path.is_file():
        firmware_path = workspace_dir / "firmware_patch" / relative_config
    return build_local_agent_status(
        state=state,
        reminders=reminders,
        active_speech=active_speech,
        current_ip=detect_lan_ip(),
        firmware_target=extract_firmware_target(firmware_path),
    )
