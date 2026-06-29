from __future__ import annotations

import json
import os
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Callable

from filelock import FileLock

from .study_modes import get_study_mode, normalize_stage


DEFAULT_STATE = {
    "studyStage": "middle",
    "stageLabel": "初中",
    "stageSource": "default",
    "stageUpdatedAt": 0,
    "xiaozhiMcpUrl": "",
    "xiaozhiMcpToken": "",
    "awayTimeoutMinutes": 15,
}

STAGE_SOURCES = frozenset({"parent", "voice", "system"})
PERSISTED_STAGE_SOURCES = STAGE_SOURCES | {"default"}


def quarantine_corrupt_file(
    path: Path,
    *,
    clock: Callable[[], float],
) -> Path:
    timestamp = int(clock() * 1000)
    backup = path.with_name(f"{path.name}.corrupt-{timestamp}")
    while backup.exists():
        timestamp += 1
        backup = path.with_name(f"{path.name}.corrupt-{timestamp}")
    path.replace(backup)
    return backup


def mask_secret(value: str) -> str:
    secret = str(value or "")
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:2]}{'*' * (len(secret) - 4)}{secret[-2:]}"


def normalize_stage_source(
    value: str,
    *,
    allow_default: bool = False,
    fallback: str | None = None,
) -> str:
    source = str(value or "").strip()
    allowed = PERSISTED_STAGE_SOURCES if allow_default else STAGE_SOURCES
    if source in allowed:
        return source
    if fallback is not None:
        if fallback not in allowed:
            raise ValueError("invalid_stage_source")
        return fallback
    raise ValueError("invalid_stage_source")


class RuntimeStateStore:
    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path)
        self.lock = FileLock(f"{self.path}.lock")
        self.clock = clock
        self._last_error: str | None = None
        self._last_corrupt_path: Path | None = None

    @property
    def diagnostic_status(self) -> dict:
        return {
            "error": self._last_error,
            "corruptPath": (
                str(self._last_corrupt_path)
                if self._last_corrupt_path is not None
                else None
            ),
        }

    def read(self) -> dict:
        with self.lock:
            state = self._read_unlocked()
        return self._with_policy(state)

    def set_stage(self, stage: str, source: str = "system") -> dict:
        normalized = normalize_stage(stage)
        normalized_source = normalize_stage_source(source)
        mode = get_study_mode(normalized)
        with self.lock:
            state = self._read_unlocked()
            state.update(
                {
                    "studyStage": normalized,
                    "stageLabel": mode.label,
                    "stageSource": normalized_source,
                    "stageUpdatedAt": int(self.clock() * 1000),
                }
            )
            self._write_unlocked(state)
        return self._with_policy(state)

    def update(self, values: dict) -> dict:
        with self.lock:
            state = self._read_unlocked()
            stage = values.get("studyStage", values.get("ageMode"))
            if stage is not None:
                normalized = normalize_stage(stage)
                normalized_source = normalize_stage_source(
                    values.get("stageSource", "system")
                )
                mode = get_study_mode(normalized)
                state.update(
                    {
                        "studyStage": normalized,
                        "stageLabel": mode.label,
                        "stageSource": normalized_source,
                        "stageUpdatedAt": int(self.clock() * 1000),
                    }
                )

            if "awayTimeoutMinutes" in values:
                minutes = int(values["awayTimeoutMinutes"])
                state["awayTimeoutMinutes"] = max(1, min(minutes, 120))
            if "xiaozhiMcpUrl" in values:
                state["xiaozhiMcpUrl"] = str(values["xiaozhiMcpUrl"] or "").strip()
            if "xiaozhiMcpToken" in values:
                state["xiaozhiMcpToken"] = str(values["xiaozhiMcpToken"] or "").strip()

            self._write_unlocked(state)
        return self._with_policy(state)

    def _read_unlocked(self) -> dict:
        state = deepcopy(DEFAULT_STATE)
        if not self.path.is_file():
            return state
        try:
            content = self.path.read_text(encoding="utf-8")
        except OSError as error:
            self._last_error = f"read_error:{type(error).__name__}"
            return state
        try:
            persisted = json.loads(content)
        except (ValueError, TypeError):
            self._quarantine_unlocked("invalid_json")
            return state
        if not isinstance(persisted, dict):
            self._quarantine_unlocked("invalid_structure")
            return state
        for key in DEFAULT_STATE:
            if key in persisted:
                state[key] = persisted[key]
        try:
            normalized = normalize_stage(state["studyStage"])
        except ValueError:
            normalized = "middle"
        mode = get_study_mode(normalized)
        state["studyStage"] = normalized
        state["stageLabel"] = mode.label
        original_source = state["stageSource"]
        state["stageSource"] = normalize_stage_source(
            original_source,
            allow_default=True,
            fallback="system",
        )
        if state["stageSource"] != original_source:
            self._write_unlocked(state)
        return state

    def _quarantine_unlocked(self, error_code: str) -> None:
        self._last_error = error_code
        try:
            self._last_corrupt_path = quarantine_corrupt_file(
                self.path,
                clock=self.clock,
            )
        except OSError as error:
            self._last_error = (
                f"{error_code}:backup_failed:{type(error).__name__}"
            )

    def _write_unlocked(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        persisted = {key: state.get(key, value) for key, value in DEFAULT_STATE.items()}
        temp_path = self.path.with_name(
            f"{self.path.name}.{os.getpid()}-{uuid.uuid4().hex}.tmp"
        )
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(persisted, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(self.path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _with_policy(state: dict) -> dict:
        result = deepcopy(state)
        result["policy"] = get_study_mode(result["studyStage"]).as_dict()
        return result
