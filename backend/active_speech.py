from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .xiaozhi_bridge import ReminderStore


DEFAULT_TIMEOUT_SECONDS = 2.0


class ActiveSpeechClient:
    def __init__(
        self,
        endpoint: str,
        device_id: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        opener: Callable = urlopen,
    ) -> None:
        self.endpoint = str(endpoint or "").strip()
        self.device_id = str(device_id or "").strip().lower()
        self.timeout = max(0.2, float(timeout))
        self.opener = opener

    @classmethod
    def from_env(cls) -> "ActiveSpeechClient":
        return cls(
            os.getenv("XIAOZHI_ACTIVE_SPEECH_URL", ""),
            os.getenv("XIAOZHI_ACTIVE_SPEECH_DEVICE_ID", ""),
            timeout=float(
                os.getenv(
                    "XIAOZHI_ACTIVE_SPEECH_TIMEOUT",
                    DEFAULT_TIMEOUT_SECONDS,
                )
            ),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint and self.device_id)

    def send(self, reminder: dict) -> dict:
        if not self.enabled:
            return {"accepted": False, "status": "disabled", "error": "disabled"}

        payload = {
            "device_id": self.device_id,
            "request_id": str(reminder.get("id") or ""),
            "text": str(reminder.get("text") or "").strip(),
            "status": "学习提醒",
            "emotion": "neutral",
            "interrupt": True,
        }
        if not payload["text"]:
            return {
                "accepted": False,
                "status": "invalid_reminder",
                "error": "text_required",
            }

        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = self._decode_response(response.read())
                status_code = int(getattr(response, "status", 200))
        except HTTPError as error:
            body = self._decode_response(error.read())
            return {
                "accepted": False,
                "status": str(body.get("error") or f"http_{error.code}"),
                "error": str(body.get("error") or f"http_{error.code}"),
            }
        except (OSError, TimeoutError, URLError) as error:
            return {
                "accepted": False,
                "status": "unavailable",
                "error": type(error).__name__,
            }

        accepted = 200 <= status_code < 300 and body.get("ok") is not False
        return {
            **body,
            "accepted": accepted,
            "status": str(
                body.get("status")
                or ("sent" if accepted else f"http_{status_code}")
            ),
        }

    @staticmethod
    def _decode_response(content: bytes) -> dict:
        if not content:
            return {}
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}


class ActiveSpeechDispatcher:
    def __init__(
        self,
        client: ActiveSpeechClient,
        reminder_store: ReminderStore,
        *,
        executor=None,
    ) -> None:
        self.client = client
        self.reminder_store = reminder_store
        self.executor = executor or ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="active-speech",
        )
        self._lock = threading.Lock()
        self._last_result = {
            "enabled": self.client.enabled,
            "lastStatus": "idle" if self.client.enabled else "disabled",
            "lastError": None,
            "lastReminderId": None,
        }

    def dispatch(self, reminder: dict) -> bool:
        if not self.client.enabled:
            return False
        self.executor.submit(self._deliver, dict(reminder))
        return True

    def _deliver(self, reminder: dict) -> None:
        result = self.client.send(reminder)
        reminder_id = str(reminder.get("id") or "")
        if result.get("accepted") and reminder_id:
            self.reminder_store.complete_direct(
                reminder_id,
                delivery="active_speech",
            )
        with self._lock:
            self._last_result = {
                "enabled": self.client.enabled,
                "lastStatus": str(result.get("status") or "unknown"),
                "lastError": (
                    None
                    if result.get("accepted")
                    else str(result.get("error") or result.get("status") or "failed")
                ),
                "lastReminderId": reminder_id or None,
            }

    def status(self) -> dict:
        with self._lock:
            return dict(self._last_result)

    def close(self) -> None:
        self.executor.shutdown(wait=False)
