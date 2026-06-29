from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StudyMode:
    key: str
    label: str
    score_threshold: int
    persist_seconds: int
    cooldown_seconds: int
    max_per_10_minutes: int
    reminder: str

    def as_dict(self) -> dict:
        return asdict(self)


STUDY_MODES = {
    "primary": StudyMode(
        key="primary",
        label="小学",
        score_threshold=55,
        persist_seconds=20,
        cooldown_seconds=180,
        max_per_10_minutes=2,
        reminder="我们先把眼睛放回题目上，完成这一小步就很棒。",
    ),
    "middle": StudyMode(
        key="middle",
        label="初中",
        score_threshold=65,
        persist_seconds=15,
        cooldown_seconds=120,
        max_per_10_minutes=3,
        reminder="先把注意力放回当前任务，我们完成这一小段再休息。",
    ),
    "high": StudyMode(
        key="high",
        label="高中",
        score_threshold=70,
        persist_seconds=25,
        cooldown_seconds=240,
        max_per_10_minutes=2,
        reminder="回到当前目标，先完成这一题组，再统一复盘。",
    ),
}

ALIASES = {
    "primary": "primary",
    "小学": "primary",
    "小学生": "primary",
    "middle": "middle",
    "初中": "middle",
    "初中生": "middle",
    "high": "high",
    "高中": "high",
    "高中生": "high",
}


def normalize_stage(value: str) -> str:
    key = ALIASES.get(str(value or "").strip().lower())
    if not key:
        raise ValueError("invalid_study_stage")
    return key


def get_study_mode(value: str) -> StudyMode:
    return STUDY_MODES[normalize_stage(value)]
