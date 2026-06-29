from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Deque

from filelock import FileLock

from .study_modes import get_study_mode


@dataclass
class _StageReminderState:
    distracted_since: float | None = None
    last_reminded_at: float | None = None
    recent_reminders: Deque[float] = field(default_factory=deque)
    pending_token: str | None = None


class ReminderPolicy:
    def __init__(
        self,
        clock: Callable[[], float] = time.time,
        *,
        state_path: str | Path | None = None,
    ) -> None:
        self.clock = clock
        self.state_path = Path(state_path) if state_path is not None else None
        self._file_lock = (
            FileLock(f"{self.state_path}.lock")
            if self.state_path is not None
            else None
        )
        self._states: dict[str, _StageReminderState] = {}
        self._lock = threading.RLock()
        self._load()

    def observe(self, payload: dict, stage: str) -> dict | None:
        with self._lock:
            mode = get_study_mode(stage)
            state = self._states.setdefault(mode.key, _StageReminderState())
            now = float(self.clock())
            score = int(payload.get("focusScore", 100))
            is_distracted = (
                payload.get("status") == "distracted"
                and score < mode.score_threshold
            )

            if not is_distracted:
                state.distracted_since = None
                return None

            if state.distracted_since is None:
                state.distracted_since = now
                return None
            if now - state.distracted_since < mode.persist_seconds:
                return None

            if (
                state.last_reminded_at is not None
                and now - state.last_reminded_at < mode.cooldown_seconds
            ):
                return None

            cutoff = now - 600
            while state.recent_reminders and state.recent_reminders[0] <= cutoff:
                state.recent_reminders.popleft()
            if len(state.recent_reminders) >= mode.max_per_10_minutes:
                return None
            if state.pending_token is not None:
                return None

            reservation = uuid.uuid4().hex
            state.pending_token = reservation
            return {
                "text": mode.reminder,
                "studyStage": mode.key,
                "stageLabel": mode.label,
                "policyVersion": "stage-v1",
                "focusScore": score,
                "createdAt": int(now * 1000),
                "_policyReservation": reservation,
            }

    def mark_sent(self, reminder: dict) -> None:
        mode = get_study_mode(str(reminder.get("studyStage") or ""))
        reservation = str(reminder.get("_policyReservation") or "")
        with self._lock:
            state = self._states.get(mode.key)
            if state is None or state.pending_token != reservation:
                raise ValueError("invalid_policy_reservation")
            now = float(self.clock())
            cutoff = now - 600
            while state.recent_reminders and state.recent_reminders[0] <= cutoff:
                state.recent_reminders.popleft()
            state.last_reminded_at = now
            state.recent_reminders.append(now)
            try:
                self._persist()
            finally:
                state.pending_token = None

    def cancel_candidate(self, reminder: dict) -> bool:
        mode = get_study_mode(str(reminder.get("studyStage") or ""))
        reservation = str(reminder.get("_policyReservation") or "")
        with self._lock:
            state = self._states.get(mode.key)
            if state is None or state.pending_token != reservation:
                return False
            state.pending_token = None
            return True

    def _load(self) -> None:
        if self.state_path is None or not self.state_path.is_file():
            return
        assert self._file_lock is not None
        with self._file_lock:
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return
        states = payload.get("states") if isinstance(payload, dict) else None
        if not isinstance(states, dict):
            return
        for stage, value in states.items():
            if not isinstance(value, dict):
                continue
            last = value.get("lastRemindedAt")
            recent = value.get("recentReminders")
            self._states[str(stage)] = _StageReminderState(
                last_reminded_at=float(last) if isinstance(last, (int, float)) else None,
                recent_reminders=deque(
                    float(item)
                    for item in recent
                    if isinstance(item, (int, float))
                )
                if isinstance(recent, list)
                else deque(),
            )

    def _persist(self) -> None:
        if self.state_path is None:
            return
        assert self._file_lock is not None
        payload = {
            "version": 1,
            "states": {
                stage: {
                    "lastRemindedAt": state.last_reminded_at,
                    "recentReminders": list(state.recent_reminders),
                }
                for stage, state in self._states.items()
            },
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_name(
            f"{self.state_path.name}.{os.getpid()}-{uuid.uuid4().hex}.tmp"
        )
        with self._file_lock:
            try:
                with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                temp_path.replace(self.state_path)
            finally:
                temp_path.unlink(missing_ok=True)
