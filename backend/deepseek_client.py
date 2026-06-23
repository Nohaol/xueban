from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from threading import Lock
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"


def _load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _setting(name: str, default: str = "") -> str:
    env_file = _load_env_file()
    return os.getenv(name) or env_file.get(name) or default


def _local_advice(payload: dict[str, Any], reason: str = "") -> dict[str, Any]:
    status = payload.get("status", "normal")
    focus_score = payload.get("focusScore", 0)
    metrics = payload.get("metrics", {}) or {}

    if status == "timeout_away":
        advice = {
            "title": "先确认休息，再决定是否介入",
            "summary": "离座已经超过阈值，建议先用温和方式确认孩子是否在合理休息。",
            "bullets": ["不要直接升级为批评。", "如果多次出现，再调整学习和休息节奏。"],
            "shouldRemind": True,
            "reminderLevel": "level_2",
            "message": "宝贝，现在还在休息吗？如果休息好了，我们准备回到学习位置。",
            "xiaozhiScript": "小智提醒你：休息好了就回到座位上，我们继续完成这一小段哦！",
            "observations": ["当前处于超时离座状态。", "需要先确认是否为合理休息。"],
            "actionPlan": ["先用温和语气确认状态。", "如果多次超时离座，再调整学习与休息节奏。"],
            "reason": "当前处于超时离座状态。",
        }
    elif status == "away":
        advice = {
            "title": "短暂离座，先观察",
            "summary": "当前更像正常短时离开，不建议立刻频繁提醒。",
            "bullets": ["等待孩子自然回到座位。", "临近学习节点时再准备温和提醒。"],
            "shouldRemind": False,
            "reminderLevel": "observe",
            "message": "",
            "xiaozhiScript": "",
            "observations": ["当前是短暂离座。", "还没有达到需要干预的强度。"],
            "actionPlan": ["继续观察孩子是否自然回到座位。", "暂不主动打断。"],
            "reason": "当前只是短暂离座。",
        }
    elif status == "distracted" or focus_score < 68 or metrics.get("gaze", 100) < 55:
        advice = {
            "title": "适合轻提醒",
            "summary": "当前出现注意力波动，建议用一句短提醒帮助孩子回到任务。",
            "bullets": ["提醒要短，不要追问原因。", "优先使用鼓励式话术。"],
            "shouldRemind": True,
            "reminderLevel": "level_1",
            "message": "小智提醒你：坐直一点，更专注哦！",
            "xiaozhiScript": "小智提醒你：坐直一点，更专注哦！",
            "observations": ["专注度或视线指标下降。", "当前更适合轻提醒，不适合追问。"],
            "actionPlan": ["发送一句短提醒。", "提醒后继续观察 1-2 分钟。"],
            "reason": "专注度或视线指标下降。",
        }
    else:
        advice = {
            "title": "保持节奏，减少干预",
            "summary": "整体状态平稳，建议继续观察，不要打断学习节奏。",
            "bullets": ["暂时不需要提醒。", "继续观察后续趋势。"],
            "shouldRemind": False,
            "reminderLevel": "observe",
            "message": "",
            "xiaozhiScript": "",
            "observations": ["当前学习状态正常。", "没有明显离座或持续分心。"],
            "actionPlan": ["保持观察。", "不要主动打断学习节奏。"],
            "reason": "当前学习状态正常。",
        }

    if reason:
        advice["fallbackReason"] = reason
    return advice


class DeepSeekAdvisor:
    def __init__(self) -> None:
        self._lock = Lock()
        self._last_called_at = 0.0
        self._last_payload_signature = ""
        self._last_result: dict[str, Any] | None = None

    @property
    def min_interval_seconds(self) -> int:
        return int(_setting("DEEPSEEK_MIN_INTERVAL_SECONDS", "120"))

    @property
    def model(self) -> str:
        return _setting("DEEPSEEK_MODEL", "deepseek-v4-flash")

    def advise(self, payload: dict[str, Any], force: bool = False) -> dict[str, Any]:
        now = time.time()
        signature = self._signature(payload)
        with self._lock:
            remaining = self.min_interval_seconds - int(now - self._last_called_at)
            if self._last_result and remaining > 0 and not force:
                return self._response(payload, self._last_result, cached=True, remaining=remaining)

            api_key = _setting("DEEPSEEK_API_KEY")
            if not api_key:
                result = _local_advice(payload, "DEEPSEEK_API_KEY 未配置，使用本地建议。")
                self._store(now, signature, result)
                return self._response(payload, result, cached=False, remaining=self.min_interval_seconds)

            try:
                result = self._call_deepseek(payload, api_key)
            except Exception as error:  # pragma: no cover - depends on network/API state.
                result = _local_advice(payload, f"DeepSeek 调用失败，使用本地建议：{error}")

            self._store(now, signature, result)
            return self._response(payload, result, cached=False, remaining=self.min_interval_seconds)

    def _store(self, called_at: float, signature: str, result: dict[str, Any]) -> None:
        self._last_called_at = called_at
        self._last_payload_signature = signature
        self._last_result = result

    def _response(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
        cached: bool,
        remaining: int,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "cached": cached,
            "model": self.model,
            "minIntervalSeconds": self.min_interval_seconds,
            "nextRefreshSeconds": max(remaining, 0),
            "payloadTimestamp": payload.get("timestamp"),
            "advice": result,
        }

    def _call_deepseek(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        base_url = _setting("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是儿童学习陪伴系统的专注度决策助手。"
                        "你只根据结构化指标给出建议，不假设画面细节。"
                        "输出必须是 JSON，不要输出 Markdown。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "根据当前专注度状态生成家长端建议和小智提醒话术。",
                            "output_schema": {
                                "title": "简短标题",
                                "summary": "一到两句判断",
                                "bullets": ["建议1", "建议2"],
                                "observations": ["基于指标的观察1", "基于指标的观察2", "基于指标的观察3"],
                                "actionPlan": ["家长或小智可以执行的步骤1", "步骤2", "步骤3"],
                                "shouldRemind": "是否建议提醒，布尔值",
                                "reminderLevel": "observe|level_1|level_2|level_3",
                                "message": "如果提醒，给小智朗读的一句话；不提醒则为空字符串",
                                "xiaozhiScript": "可直接发给孩子听的小智话术，建议以“小智提醒你：”开头；不提醒则为空字符串",
                                "reason": "为什么这么判断",
                            },
                            "state": payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(request_payload).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return self._normalize_result(parsed)

    def _normalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        bullets = result.get("bullets")
        if not isinstance(bullets, list):
            bullets = []
        observations = result.get("observations")
        if not isinstance(observations, list):
            observations = []
        action_plan = result.get("actionPlan")
        if not isinstance(action_plan, list):
            action_plan = []
        message = str(result.get("message") or "")
        xiaozhi_script = str(result.get("xiaozhiScript") or message)
        return {
            "title": str(result.get("title") or "AI 建议"),
            "summary": str(result.get("summary") or ""),
            "bullets": [str(item) for item in bullets[:3]],
            "observations": [str(item) for item in observations[:4]],
            "actionPlan": [str(item) for item in action_plan[:4]],
            "shouldRemind": bool(result.get("shouldRemind", False)),
            "reminderLevel": str(result.get("reminderLevel") or "observe"),
            "message": message,
            "xiaozhiScript": xiaozhi_script,
            "reason": str(result.get("reason") or ""),
        }

    def _signature(self, payload: dict[str, Any]) -> str:
        compact = {
            "status": payload.get("status"),
            "focusScore": payload.get("focusScore"),
            "awaySeconds": payload.get("awaySeconds"),
            "metrics": payload.get("metrics"),
        }
        return json.dumps(compact, sort_keys=True, ensure_ascii=False)
