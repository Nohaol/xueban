from __future__ import annotations

import asyncio
import json
from urllib.request import Request, urlopen


STAGES = {
    "primary": {
        "label": "小学",
        "aliases": (
            "小学",
            "小学生",
            "一年级",
            "二年级",
            "三年级",
            "四年级",
            "五年级",
            "六年级",
        ),
    },
    "middle": {
        "label": "初中",
        "aliases": (
            "初中",
            "初中生",
            "初一",
            "初二",
            "初三",
            "七年级",
            "八年级",
            "九年级",
        ),
    },
    "high": {
        "label": "高中",
        "aliases": (
            "高中",
            "高中生",
            "高一",
            "高二",
            "高三",
        ),
    },
}


def detect_study_stage(text: str) -> str | None:
    normalized = str(text or "").strip()
    matches = {
        stage
        for stage, definition in STAGES.items()
        if any(alias in normalized for alias in definition["aliases"])
    }
    if len(matches) != 1:
        return None
    return matches.pop()


def stage_label(stage: str) -> str:
    return str(STAGES[stage]["label"])


def build_stage_confirmation(stage: str) -> str:
    return f"已进入{stage_label(stage)}模式。"


def _request_parent_stage(method: str, payload: dict | None = None) -> dict:
    url = "http://127.0.0.1:8000/study-stage"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=method,
    )
    with urlopen(request, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


async def set_parent_stage(stage: str) -> dict:
    return await asyncio.to_thread(
        _request_parent_stage,
        "POST",
        {"stage": stage, "source": "voice"},
    )


async def get_parent_stage() -> dict:
    return await asyncio.to_thread(_request_parent_stage, "GET")
