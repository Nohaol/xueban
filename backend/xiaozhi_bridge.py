from __future__ import annotations

import json
import os
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Callable

from filelock import FileLock

from .runtime_state import RuntimeStateStore, quarantine_corrupt_file


class ReminderStore:
    def __init__(
        self,
        path: str | Path,
        *,
        state_store: RuntimeStateStore,
        clock: Callable[[], float] = time.time,
        lease_seconds: int = 60,
    ) -> None:
        self.path = Path(path)
        self.lock = FileLock(f"{self.path}.lock")
        self.state_store = state_store
        self.clock = clock
        self.lease_seconds = max(1, int(lease_seconds))
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

    def enqueue(
        self,
        command: str,
        text: str,
        focus_payload: dict | None = None,
        *,
        reminder_metadata: dict | None = None,
    ) -> dict:
        if reminder_metadata is None:
            state = self.state_store.read()
            metadata = {
                "studyStage": state["studyStage"],
                "stageLabel": state["stageLabel"],
                "policyVersion": "stage-v1",
            }
        else:
            required = {"studyStage", "stageLabel", "policyVersion"}
            if not required.issubset(reminder_metadata):
                raise ValueError("invalid_reminder_metadata")
            metadata = reminder_metadata
        now_ms = int(self.clock() * 1000)
        item = {
            "id": uuid.uuid4().hex,
            "command": str(command),
            "text": str(text),
            "focusPayload": deepcopy(focus_payload) if focus_payload else {},
            "studyStage": metadata["studyStage"],
            "stageLabel": metadata["stageLabel"],
            "policyVersion": metadata["policyVersion"],
            "status": "pending",
            "createdAt": now_ms,
            "deliveredAt": None,
            "leaseExpiresAt": None,
            "acknowledgedAt": None,
            "spoken": None,
        }
        with self.lock:
            queue = self._read_unlocked()
            queue["items"].append(item)
            self._write_unlocked(queue)
        return deepcopy(item)

    def pop_next(self) -> dict:
        with self.lock:
            queue = self._read_unlocked()
            now_ms = int(self.clock() * 1000)
            self._recover_expired_unlocked(queue, now_ms)
            item = next(
                (candidate for candidate in queue["items"] if candidate.get("status") == "pending"),
                None,
            )
            if item is None:
                return {"hasReminder": False}
            item["status"] = "delivered"
            item["deliveredAt"] = now_ms
            item["leaseExpiresAt"] = now_ms + self.lease_seconds * 1000
            self._write_unlocked(queue)
            result = deepcopy(item)

        result.update(
            {
                "hasReminder": True,
                "reminderId": result["id"],
                "reminderText": result["text"],
            }
        )
        return result

    def acknowledge(self, reminder_id: str, spoken: bool = True) -> dict:
        with self.lock:
            queue = self._read_unlocked()
            if self._recover_expired_unlocked(
                queue,
                int(self.clock() * 1000),
            ):
                self._write_unlocked(queue)
            item = next(
                (
                    candidate
                    for candidate in queue["items"]
                    if candidate.get("id") == reminder_id
                ),
                None,
            )
            if item is None:
                return {
                    "success": False,
                    "acknowledged": False,
                    "error": "reminder_not_found",
                }
            status = item.get("status")
            if status == "pending":
                return {
                    "success": False,
                    "acknowledged": False,
                    "error": "invalid_reminder_state",
                }
            if status in {"spoken", "skipped", "dismissed"}:
                return {
                    "success": True,
                    "acknowledged": True,
                    "idempotent": True,
                    "item": deepcopy(item),
                }
            if status != "delivered":
                return {
                    "success": False,
                    "acknowledged": False,
                    "error": "invalid_reminder_state",
                }
            item["status"] = "spoken" if spoken else "skipped"
            item["spoken"] = bool(spoken)
            item["acknowledgedAt"] = int(self.clock() * 1000)
            self._write_unlocked(queue)
            result = deepcopy(item)
        return {
            "success": True,
            "acknowledged": True,
            "idempotent": False,
            "item": result,
        }

    def snapshot(self) -> dict:
        with self.lock:
            queue = self._read_unlocked()
            if self._recover_expired_unlocked(
                queue,
                int(self.clock() * 1000),
            ):
                self._write_unlocked(queue)
        items = deepcopy(queue["items"])
        return {
            "pendingCount": sum(item.get("status") == "pending" for item in items),
            "deliveredCount": sum(item.get("status") == "delivered" for item in items),
            "completedCount": sum(
                item.get("status") in {"spoken", "skipped", "dismissed"}
                for item in items
            ),
            "items": items,
        }

    def _read_unlocked(self) -> dict:
        if not self.path.is_file():
            return {"version": 1, "items": []}
        try:
            content = self.path.read_text(encoding="utf-8")
        except OSError as error:
            self._last_error = f"read_error:{type(error).__name__}"
            return {"version": 1, "items": []}
        try:
            queue = json.loads(content)
        except (ValueError, TypeError):
            self._quarantine_unlocked("invalid_json")
            return {"version": 1, "items": []}
        if (
            not isinstance(queue, dict)
            or not isinstance(queue.get("items"), list)
            or not all(isinstance(item, dict) for item in queue["items"])
        ):
            self._quarantine_unlocked("invalid_structure")
            return {"version": 1, "items": []}
        return queue

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

    @staticmethod
    def _recover_expired_unlocked(queue: dict, now_ms: int) -> bool:
        changed = False
        for item in queue["items"]:
            if (
                item.get("status") == "delivered"
                and isinstance(item.get("leaseExpiresAt"), (int, float))
                and item["leaseExpiresAt"] <= now_ms
            ):
                item["status"] = "pending"
                item["deliveredAt"] = None
                item["leaseExpiresAt"] = None
                changed = True
        return changed

    def _write_unlocked(self, queue: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(
            f"{self.path.name}.{os.getpid()}-{uuid.uuid4().hex}.tmp"
        )
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(queue, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(self.path)
        finally:
            temp_path.unlink(missing_ok=True)
