from __future__ import annotations

import base64
import json
import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Deque, Iterator

try:
    import cv2  # type: ignore
except ImportError:  # pragma: no cover
    cv2 = None

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover
    np = None

try:
    import mediapipe  # type: ignore
    from mediapipe.tasks import python as mp_python  # type: ignore
    from mediapipe.tasks.python import vision as mp_vision  # type: ignore
except ImportError:  # pragma: no cover
    mediapipe = None
    mp_python = None
    mp_vision = None

try:
    from focus_lab.focus_features import (  # type: ignore
        FocusAnalyzer,
        compute_features,
        landmark_to_ndarray,
        no_face_features,
    )
except ImportError:  # pragma: no cover
    FocusAnalyzer = None
    compute_features = None
    landmark_to_ndarray = None
    no_face_features = None

from .schemas import FocusMetrics, FocusPayload
from .reminder_policy import ReminderPolicy
from .runtime_state import RuntimeStateStore, mask_secret
from .xiaozhi_bridge import ReminderStore


PLACEHOLDER_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBAQEA8QDw8PDw8QDw8PDw8QFREWFhURFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGxAQGi0fHyUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAgMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6A//xAAXEAADAQAAAAAAAAAAAAAAAAAAAREC/9oACAEBAAEFAmcf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAwEBPwEf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwEf/8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQAGPwJf/8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQABPyFf/9k="
)


@dataclass
class EngineConfig:
    student_label: str = os.getenv("FOCUS_STUDENT_LABEL", "学生 A")
    camera_source: str = os.getenv("FOCUS_CAMERA_SOURCE", "0")
    analyzer: str = os.getenv("FOCUS_ANALYZER", "mediapipe")
    mediapipe_model_path: str = os.getenv(
        "FOCUS_MEDIAPIPE_MODEL",
        str(Path(__file__).resolve().parent.parent / "focus_lab" / "models" / "face_landmarker.task"),
    )
    frame_width: int = int(os.getenv("FOCUS_FRAME_WIDTH", "960"))
    frame_height: int = int(os.getenv("FOCUS_FRAME_HEIGHT", "540"))
    analysis_fps: float = float(os.getenv("FOCUS_ANALYSIS_FPS", "10"))
    focus_window_seconds: float = float(os.getenv("FOCUS_WINDOW_SECONDS", "30"))
    calibration_seconds: float = float(os.getenv("FOCUS_CALIBRATION_SECONDS", "12"))
    away_timeout_seconds: int = int(os.getenv("FOCUS_AWAY_TIMEOUT_SECONDS", "900"))
    face_grace_seconds: float = float(os.getenv("FOCUS_FACE_GRACE_SECONDS", "3"))
    jpeg_quality: int = int(os.getenv("FOCUS_JPEG_QUALITY", "82"))
    mock_mode: bool = os.getenv("FOCUS_FORCE_MOCK", "0") == "1"
    local_probe_count: int = int(os.getenv("FOCUS_LOCAL_PROBE_COUNT", "5"))
    source_retry_seconds: float = float(os.getenv("FOCUS_SOURCE_RETRY_SECONDS", "2.5"))
    stream_open_timeout_ms: int = int(os.getenv("FOCUS_STREAM_OPEN_TIMEOUT_MS", "1500"))
    stream_read_timeout_ms: int = int(os.getenv("FOCUS_STREAM_READ_TIMEOUT_MS", "900"))


@dataclass
class VideoSource:
    source_id: str
    source_type: str
    label: str
    location: str
    transport: str = "stream"
    is_builtin: bool = False
    is_selected: bool = False
    status: str = "idle"
    note: str = ""


class FocusEngine:
    def __init__(
        self,
        config: EngineConfig | None = None,
        *,
        state_store: RuntimeStateStore | None = None,
        reminder_store: ReminderStore | None = None,
        reminder_policy: ReminderPolicy | None = None,
        active_speech=None,
    ) -> None:
        self.config = config or EngineConfig()
        runtime_dir = Path(
            os.getenv(
                "XUEBAN_RUNTIME_DIR",
                Path(__file__).resolve().parent / "runtime",
            )
        )
        self.state_store = state_store or RuntimeStateStore(
            runtime_dir / "runtime_state.json"
        )
        self.reminder_store = reminder_store or ReminderStore(
            runtime_dir / "xiaozhi_reminders.json",
            state_store=self.state_store,
        )
        self.reminder_policy = reminder_policy or ReminderPolicy(
            state_path=runtime_dir / "reminder_policy.json"
        )
        self.active_speech = active_speech
        persisted_state = self.state_store.read()
        self.config.away_timeout_seconds = (
            int(persisted_state["awayTimeoutMinutes"]) * 60
        )
        self._reminder_stage_cache: str | None = None
        self._reminder_stage_cache_at = 0.0
        self._last_reminder_error: str | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture = None
        self._frame_counter = 0
        self._last_control = {"command": "", "text": "", "received_at": 0.0}
        self._mode = "boot"
        self._away_started_at: float | None = None
        self._presence_history: Deque[tuple[float, bool]] = deque()
        self._motion_history: Deque[float] = deque(maxlen=12)
        self._recent_face_boxes: Deque[tuple[int, int, int, int]] = deque(maxlen=8)
        self._last_face_seen_at: float = 0.0
        self._last_face_box: tuple[int, int, int, int] | None = None
        self._sources: dict[str, VideoSource] = {}
        self._current_source_id = "local-default"
        self._last_source_error = ""
        self._capture_signature = ""
        self._source_retry_after = 0.0
        self._source_switch_started_at = 0.0
        self._prev_gray = None
        self._mp_landmarker = None
        self._mp_last_timestamp_ms = 0
        self._mp_error = ""
        self._calibration_session: dict | None = None
        self._focus_analyzer = self._create_focus_analyzer()

        self._face_cascade = None
        self._eye_cascade = None
        if cv2 is not None:
          self._face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
          self._eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

        self._seed_builtin_sources()
        self._latest_jpeg = PLACEHOLDER_JPEG
        self._latest_payload = self._build_boot_payload()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="focus-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._release_capture()
        close = getattr(self.active_speech, "close", None)
        if callable(close):
            close()

    def get_payload(self) -> dict:
        with self._lock:
            if hasattr(self._latest_payload, "model_dump"):
                payload = self._latest_payload.model_dump()
            else:
                payload = self._latest_payload.dict()
        state = self.state_store.read()
        payload["studyStage"] = state["studyStage"]
        payload["stageLabel"] = state["stageLabel"]
        return payload

    def get_settings(self) -> dict:
        return self._public_settings(self.state_store.read())

    def update_settings(self, settings: dict) -> dict:
        state = self.state_store.update(settings)
        self.config.away_timeout_seconds = int(state["awayTimeoutMinutes"]) * 60
        return self._public_settings(state)

    def process_automatic_reminder(self, payload: dict | FocusPayload) -> dict | None:
        if hasattr(payload, "model_dump"):
            focus_payload = payload.model_dump()
        elif hasattr(payload, "dict"):
            focus_payload = payload.dict()
        else:
            focus_payload = dict(payload)
        try:
            stage = self._cached_reminder_stage()
        except Exception as error:
            self._record_reminder_error("state_read", error)
            return None
        try:
            reminder = self.reminder_policy.observe(focus_payload, stage)
        except Exception as error:
            self._record_reminder_error("policy_observe", error)
            return None
        if reminder is not None:
            try:
                queued_reminder = self.reminder_store.enqueue(
                    "managed_ai_reminder",
                    reminder["text"],
                    focus_payload,
                    reminder_metadata=reminder,
                )
            except Exception as error:
                cancel_candidate = getattr(
                    self.reminder_policy,
                    "cancel_candidate",
                    None,
                )
                if callable(cancel_candidate):
                    try:
                        cancel_candidate(reminder)
                    except Exception:
                        pass
                self._record_reminder_error("enqueue", error)
                return None
            mark_sent = getattr(self.reminder_policy, "mark_sent", None)
            if callable(mark_sent):
                try:
                    mark_sent(reminder)
                except Exception as error:
                    self._record_reminder_error("policy_commit", error)
            self.dispatch_active_speech(queued_reminder)
            reminder.pop("_policyReservation", None)
        return reminder

    def dispatch_active_speech(self, reminder: dict) -> bool:
        dispatch = getattr(self.active_speech, "dispatch", None)
        if not callable(dispatch):
            return False
        try:
            return bool(dispatch(reminder))
        except Exception as error:
            self._record_reminder_error("active_speech_dispatch", error)
            return False

    def active_speech_status(self) -> dict:
        status = getattr(self.active_speech, "status", None)
        if not callable(status):
            return {
                "enabled": False,
                "lastStatus": "disabled",
                "lastError": None,
                "lastReminderId": None,
            }
        return status()

    @property
    def last_reminder_error(self) -> str | None:
        return self._last_reminder_error

    def _cached_reminder_stage(self) -> str:
        now = time.monotonic()
        if (
            self._reminder_stage_cache is not None
            and now - self._reminder_stage_cache_at < 1.0
        ):
            return self._reminder_stage_cache
        state = self.state_store.read()
        stage = str(state["studyStage"])
        self._reminder_stage_cache = stage
        self._reminder_stage_cache_at = now
        return stage

    def _record_reminder_error(self, operation: str, error: Exception) -> None:
        self._last_reminder_error = f"{operation}:{type(error).__name__}"

    @staticmethod
    def _public_settings(state: dict) -> dict:
        token = str(state.get("xiaozhiMcpToken") or "")
        masked_token = mask_secret(token)
        url = str(state.get("xiaozhiMcpUrl") or "")
        mcp_prefix = "wss://api.xiaozhi.me/mcp/"
        if url.startswith(mcp_prefix):
            url = mcp_prefix
        return {
            "awayTimeoutMinutes": int(state["awayTimeoutMinutes"]),
            "xiaozhiMcpUrl": url,
            "xiaozhiMcpToken": masked_token,
            "xiaozhiMcpTokenConfigured": bool(token),
            "ageMode": state["studyStage"],
            "studyStage": state["studyStage"],
            "stageLabel": state["stageLabel"],
            "stageSource": state["stageSource"],
            "stageUpdatedAt": state["stageUpdatedAt"],
            "policy": state["policy"],
        }

    def get_snapshot_bytes(self) -> bytes:
        with self._lock:
            return self._latest_jpeg

    def video_feed(self) -> Iterator[bytes]:
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while not self._stop_event.is_set():
            yield boundary + self.get_snapshot_bytes() + b"\r\n"
            time.sleep(1 / max(self.config.analysis_fps, 1))

    def handle_control(self, command: str, text: str | None = None) -> dict:
        received_at = time.time()
        self._last_control = {"command": command, "text": text or "", "received_at": received_at}
        if command == "reset_session":
            self.reset_session()
        elif command == "refresh_stream":
            self._reset_capture()
        elif command == "calibrate_posture":
            return self.start_calibration()
        return {
            "accepted": True,
            "command": command,
            "text": text or "",
            "receivedAt": int(received_at * 1000),
            "mode": self._mode,
            "sourceId": self._current_source_id,
        }

    def start_calibration(self) -> dict:
        now = time.time()
        self._calibration_session = {
            "sourceId": self._current_source_id,
            "startedAt": now,
            "duration": max(self.config.calibration_seconds, 3.0),
            "samples": [],
            "status": "collecting",
        }
        return {
            "accepted": True,
            "command": "calibrate_posture",
            "sourceId": self._current_source_id,
            "duration": self._calibration_session["duration"],
            "message": "Calibration started. Keep the normal study posture.",
        }

    def list_sources(self) -> list[dict]:
        return [self._source_payload(source) for source in self._sources.values()]

    def get_current_source(self) -> dict:
        return self._source_payload(self._sources[self._current_source_id])

    def probe_source(self, source_id: str) -> dict:
        if source_id not in self._sources:
            raise KeyError(source_id)

        source = self._sources[source_id]
        ok, note = self._probe_source_frame(source)
        source.status = "live" if ok else "offline"
        source.note = note
        return {
            "ok": ok,
            "source": self._source_payload(source),
            "note": note,
        }

    def add_network_source(self, label: str, url: str, transport: str) -> dict:
        for source in self._sources.values():
            if source.source_type == "network_camera" and source.location == url and source.transport == transport:
                source.label = label
                source.note = "用户添加的网络摄像头。"
                return self._source_payload(source)

        source_id = self._make_network_source_id(label)
        source = VideoSource(
            source_id=source_id,
            source_type="network_camera",
            label=label,
            location=url,
            transport=transport,
            is_builtin=False,
            is_selected=False,
            status="idle",
            note="用户添加的网络摄像头。",
        )
        self._sources[source_id] = source
        return self._source_payload(source)

    def select_source(self, source_id: str) -> dict:
        if source_id not in self._sources:
            raise KeyError(source_id)
        self._current_source_id = source_id
        self._calibration_session = None
        self._presence_history.clear()
        self._motion_history.clear()
        self._recent_face_boxes.clear()
        self._last_face_seen_at = 0.0
        self._last_face_box = None
        self._away_started_at = None
        self._focus_analyzer = self._create_focus_analyzer()
        self._prev_gray = None
        self._last_source_error = ""
        self._source_retry_after = 0.0
        self._source_switch_started_at = time.time()
        self._mark_selected_source(source_id)
        self._reset_capture()
        with self._lock:
            self._latest_jpeg = PLACEHOLDER_JPEG
        return self._source_payload(self._sources[source_id])

    def reset_session(self) -> dict:
        if "local-default" in self._sources:
            self._current_source_id = "local-default"
        else:
            self._current_source_id = next(iter(self._sources))

        self._calibration_session = None
        self._presence_history.clear()
        self._motion_history.clear()
        self._recent_face_boxes.clear()
        self._last_face_seen_at = 0.0
        self._last_face_box = None
        self._away_started_at = None
        self._focus_analyzer = self._create_focus_analyzer()
        self._prev_gray = None
        self._last_source_error = ""
        self._source_retry_after = 0.0
        self._source_switch_started_at = time.time()
        self._mode = "boot"
        self._frame_counter = 0
        self._mark_selected_source(self._current_source_id)
        self._reset_capture()
        for source in self._sources.values():
            if source.source_type == "network_camera":
                source.status = "idle"
        current = self._sources[self._current_source_id]
        current.status = "idle"
        current.note = "已重置为默认本机摄像头，等待第一帧画面。"
        with self._lock:
            self._latest_jpeg = PLACEHOLDER_JPEG
            self._latest_payload = self._build_boot_payload()
        return self._source_payload(current)

    def delete_source(self, source_id: str) -> dict:
        if source_id not in self._sources:
            raise KeyError(source_id)

        source = self._sources[source_id]
        if source.is_builtin:
            raise ValueError("builtin_source_cannot_be_deleted")

        was_selected = source.is_selected
        del self._sources[source_id]

        if was_selected:
            fallback_id = next(iter(self._sources))
            self._current_source_id = fallback_id
            self._mark_selected_source(fallback_id)
            self._reset_capture()

        return self._source_payload(self._sources[self._current_source_id])

    def _preferred_analyzer(self) -> str:
        return self.config.analyzer.strip().lower()

    def _wants_mediapipe(self) -> bool:
        return self._preferred_analyzer() != "haar"

    def _can_use_haar(self) -> bool:
        return self._face_cascade is not None and not self._face_cascade.empty()

    def _can_use_mediapipe(self) -> bool:
        if not self._wants_mediapipe():
            return False
        if mediapipe is None or mp_python is None or mp_vision is None:
            self._mp_error = "MediaPipe is not installed."
            return False
        if FocusAnalyzer is None or compute_features is None or landmark_to_ndarray is None or no_face_features is None:
            self._mp_error = "focus_lab feature analyzer is unavailable."
            return False
        if not Path(self.config.mediapipe_model_path).is_file():
            self._mp_error = f"MediaPipe model not found: {self.config.mediapipe_model_path}"
            return False
        return True

    def _create_focus_analyzer(self):
        if FocusAnalyzer is None:
            return None
        calibration_path = self._calibration_path(self._current_source_id)
        return FocusAnalyzer(
            window_seconds=self.config.focus_window_seconds,
            fps_estimate=max(int(self.config.analysis_fps), 1),
            calibration_path=str(calibration_path) if calibration_path.is_file() else None,
        )

    def _safe_source_key(self, source_id: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in source_id)

    def _calibration_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "focus_lab" / "config" / "sources"

    def _calibration_path(self, source_id: str) -> Path:
        return self._calibration_dir() / f"{self._safe_source_key(source_id)}.json"

    def _source_payload(self, source: VideoSource) -> dict:
        payload = asdict(source)
        calibration_path = self._calibration_path(source.source_id)
        calibrated_at = None
        sample_count = 0
        if calibration_path.is_file():
            try:
                calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
                calibrated_at = int(calibration.get("createdAt") or 0) or None
                sample_count = int(calibration.get("sampleCount") or 0)
            except (OSError, ValueError, TypeError):
                calibrated_at = None
                sample_count = 0
        payload["calibration"] = {
            "calibrated": calibrated_at is not None,
            "calibratedAt": calibrated_at,
            "sampleCount": sample_count,
        }
        return payload

    def _ensure_mediapipe_landmarker(self) -> bool:
        if self._mp_landmarker is not None:
            return True
        if not self._can_use_mediapipe():
            return False
        try:
            base_options = mp_python.BaseOptions(model_asset_path=self.config.mediapipe_model_path)
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
            )
            self._mp_landmarker = mp_vision.FaceLandmarker.create_from_options(options)
            self._mp_error = ""
            return True
        except Exception as error:  # pragma: no cover - depends on local MediaPipe runtime.
            self._mp_landmarker = None
            self._mp_error = f"MediaPipe initialization failed: {error}"
            return False

    def _close_mediapipe_landmarker(self) -> None:
        return

    def _seed_builtin_sources(self) -> None:
        configured_index = int(self.config.camera_source) if self.config.camera_source.isdigit() else 0
        candidate_indexes = [configured_index]
        for idx in range(max(self.config.local_probe_count, 2)):
            if len(candidate_indexes) >= 2:
                break
            if idx not in candidate_indexes:
                candidate_indexes.append(idx)

        for order, camera_index in enumerate(candidate_indexes):
            source_id = "local-default" if order == 0 else f"local-{camera_index}"
            self._sources[source_id] = VideoSource(
                source_id=source_id,
                source_type="local_camera",
                label="本机摄像头" if order == 0 else f"本机摄像头 {camera_index}",
                location=str(camera_index),
                transport="stream",
                is_builtin=True,
                is_selected=order == 0,
                status="idle",
                note="固定本机摄像头槽位，首次读取画面时确认可用性。",
            )

    def _probe_local_cameras(self) -> list[int]:
        if cv2 is None:
            return []

        found = []
        for index in range(self.config.local_probe_count):
            capture = self._open_local_capture(index)
            if not capture or not capture.isOpened():
                if capture:
                    capture.release()
                continue
            ok, frame = capture.read()
            capture.release()
            if ok and frame is not None:
                found.append(index)
        return found

    def _mark_selected_source(self, source_id: str) -> None:
        for key, source in self._sources.items():
            source.is_selected = key == source_id

    def _run_loop(self) -> None:
        target_interval = 1.0 / max(self.config.analysis_fps, 1)
        while not self._stop_event.is_set():
            started_at = time.time()
            payload, frame = self._next_state()
            self.process_automatic_reminder(payload)
            jpeg = self._encode_frame(frame)
            with self._lock:
                self._latest_payload = payload
                self._latest_jpeg = jpeg
                self._frame_counter += 1
            elapsed = time.time() - started_at
            time.sleep(max(target_interval - elapsed, 0.01))

    def _next_state(self) -> tuple[FocusPayload, object | None]:
        source = self._sources[self._current_source_id]
        can_analyze = (
            not self.config.mock_mode
            and cv2 is not None
            and np is not None
            and (self._can_use_mediapipe() or self._can_use_haar())
        )
        if not can_analyze:
            self._mode = "mock"
            source.status = "mock"
            source.note = self._why_mock_mode()
            return self._build_mock_state(source)

        frame = self._read_source_frame(source)
        if frame is None:
            self._mode = "mock"
            source.status = "connecting" if time.time() < self._source_retry_after else "offline"
            source.note = self._last_source_error or "无法打开或读取当前视频源。"
            return self._build_mock_state(source)

        source.status = "live"
        source.note = "视频流已进入本地视觉节点，正在持续分析。"
        return self._analyze_frame(frame, source)

    def _build_boot_payload(self) -> FocusPayload:
        current = self._sources.get(self._current_source_id)
        return FocusPayload(
            timestamp=int(time.time() * 1000),
            studentLabel=self.config.student_label,
            status="normal",
            focusScore=76,
            awaySeconds=0,
            eventText="视觉节点正在启动，等待第一帧画面。",
            metrics=FocusMetrics(gaze=78, posture=74, stability=79, presence=80),
            sourceId=self._current_source_id,
            sourceLabel=current.label if current else "本机摄像头",
            engineMode="boot",
        )

    def _build_mock_state(self, source: VideoSource) -> tuple[FocusPayload, object | None]:
        now = time.time()
        cycle = int(now) % 28
        if cycle < 7:
            status = "flow"
            metrics = FocusMetrics(gaze=94, posture=91, stability=87, presence=100)
            focus_score = 93
            away_seconds = 0
            event_text = "检测到持续稳定的专注状态。"
        elif cycle < 14:
            status = "normal"
            metrics = FocusMetrics(gaze=82, posture=79, stability=83, presence=100)
            focus_score = 82
            away_seconds = 0
            event_text = "学习节奏平稳。"
        elif cycle < 20:
            status = "distracted"
            metrics = FocusMetrics(gaze=58, posture=63, stability=66, presence=96)
            focus_score = 64
            away_seconds = 0
            event_text = "注意力有轻微漂移，稍后可以温和提醒。"
        elif cycle < 24:
            status = "away"
            metrics = FocusMetrics(gaze=16, posture=24, stability=38, presence=60)
            focus_score = 24
            away_seconds = 6 * 60 + (cycle - 20) * 12
            event_text = "检测到短暂离座。"
        else:
            status = "timeout_away"
            metrics = FocusMetrics(gaze=8, posture=14, stability=25, presence=28)
            focus_score = 12
            away_seconds = self.config.away_timeout_seconds + (cycle - 24) * 20
            event_text = "离座时间超过阈值。"

        payload = FocusPayload(
            timestamp=int(now * 1000),
            studentLabel=self.config.student_label,
            status=status,
            focusScore=focus_score,
            awaySeconds=away_seconds,
            eventText=event_text,
            metrics=metrics,
            sourceId=source.source_id,
            sourceLabel=source.label,
            engineMode="mock",
        )
        return payload, self._render_mock_frame(payload, source)

    def _analyze_frame(self, frame: object, source: VideoSource) -> tuple[FocusPayload, object]:
        if self._ensure_mediapipe_landmarker():
            return self._analyze_frame_mediapipe(frame, source)

        if not self._can_use_haar():
            self._mode = "mock"
            source.status = "mock"
            source.note = self._mp_error or "No available visual analyzer."
            return self._build_mock_state(source)

        assert cv2 is not None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        detected = len(faces) > 0
        now = time.time()
        face_box = None
        if detected:
            face_box = max(faces, key=lambda box: box[2] * box[3])
            face_box = tuple(int(v) for v in face_box)
            self._last_face_seen_at = now
            self._last_face_box = face_box
        elif self._last_face_box is not None and now - self._last_face_seen_at <= self.config.face_grace_seconds:
            face_box = self._last_face_box
            detected = True

        self._presence_history.append((now, detected))
        while self._presence_history and now - self._presence_history[0][0] > 300:
            self._presence_history.popleft()

        away_seconds = self._compute_away_seconds(detected, now)
        presence_score = self._presence_score()

        gaze_score = 8
        posture_score = 12
        stability_score = self._estimate_motion(gray, None)
        event_text = "没有检测到人脸，当前座位视为无人。"
        if detected:
            gaze_score = self._estimate_gaze(gray, face_box)
            posture_score = self._estimate_posture(face_box, frame.shape[1], frame.shape[0])
            stability_score = self._estimate_motion(gray, face_box)
            if len(faces) == 0:
                gaze_score = min(gaze_score, 62)
                event_text = "短暂未检测到正脸，可能只是转头或遮挡，暂不按离座处理。"
            else:
                event_text = self._compose_simple_event(face_box, gaze_score, posture_score, stability_score)
            self._recent_face_boxes.append(face_box)

        focus_score = int(
            round(
                gaze_score * 0.35
                + posture_score * 0.22
                + stability_score * 0.18
                + presence_score * 0.25
            )
        )

        status = self._resolve_status(focus_score, gaze_score, away_seconds)
        if status == "away":
            focus_score = min(focus_score, 35)
        if status == "timeout_away":
            focus_score = min(focus_score, 15)

        metrics = FocusMetrics(
            gaze=gaze_score,
            posture=posture_score,
            stability=stability_score,
            presence=presence_score,
        )
        payload = FocusPayload(
            timestamp=int(now * 1000),
            studentLabel=self.config.student_label,
            status=status,
            focusScore=focus_score,
            awaySeconds=away_seconds,
            eventText=event_text,
            metrics=metrics,
            sourceId=source.source_id,
            sourceLabel=source.label,
            engineMode="camera",
        )
        annotated = self._annotate_frame(frame.copy(), payload, face_box)
        self._prev_gray = gray
        return payload, annotated

    def _analyze_frame_mediapipe(self, frame: object, source: VideoSource) -> tuple[FocusPayload, object]:
        assert cv2 is not None
        assert np is not None
        assert mediapipe is not None
        assert self._mp_landmarker is not None
        assert compute_features is not None
        assert landmark_to_ndarray is not None
        assert no_face_features is not None

        now = time.time()
        timestamp_ms = max(int(now * 1000), self._mp_last_timestamp_ms + 1)
        self._mp_last_timestamp_ms = timestamp_ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)
        result = self._mp_landmarker.detect_for_video(mp_image, timestamp_ms)

        height, width = frame.shape[:2]
        has_face = len(result.face_landmarks) > 0
        landmarks = result.face_landmarks[0] if has_face else None
        transform = result.facial_transformation_matrixes[0] if (
            has_face
            and result.facial_transformation_matrixes
            and len(result.facial_transformation_matrixes) > 0
        ) else None

        if self._focus_analyzer is None:
            self._focus_analyzer = self._create_focus_analyzer()

        if has_face and landmarks is not None:
            lm_3d = landmark_to_ndarray(landmarks)
            features = compute_features(
                lm_3d,
                (height, width),
                transform_matrix=transform,
                cal=self._focus_analyzer.cal if self._focus_analyzer else None,
                nose_history=self._focus_analyzer.nose_history if self._focus_analyzer else None,
            )
            if self._focus_analyzer is not None:
                nose_xy = np.array([float(landmarks[1].x), float(landmarks[1].y)])
                self._focus_analyzer.nose_history.append(nose_xy)
                if len(self._focus_analyzer.nose_history) > self._focus_analyzer.window_frames:
                    self._focus_analyzer.nose_history.pop(0)
        else:
            features = no_face_features()

        calibration_message = self._record_calibration_sample(has_face, features, source, now)
        state = self._focus_analyzer.update(has_face, features) if self._focus_analyzer is not None else {
            "status": "away",
            "score": 0,
            "recentFaceRatio": 0,
            "subScores": {},
            "reasonCodes": ["face_not_visible"],
        }

        self._presence_history.append((now, has_face))
        while self._presence_history and now - self._presence_history[0][0] > 300:
            self._presence_history.popleft()

        away_seconds = self._compute_away_seconds(has_face, now)
        status = self._map_mediapipe_status(state, away_seconds)
        focus_score = self._clamp(float(state.get("score", 0)))
        if status == "away":
            focus_score = min(focus_score, 35)
        if status == "timeout_away":
            focus_score = min(focus_score, 15)

        metrics = self._metrics_from_mediapipe_state(state, features)
        event_text = calibration_message or self._compose_mediapipe_event(status, state, features)
        payload = FocusPayload(
            timestamp=timestamp_ms,
            studentLabel=self.config.student_label,
            status=status,
            focusScore=focus_score,
            awaySeconds=away_seconds,
            eventText=event_text,
            metrics=metrics,
            sourceId=source.source_id,
            sourceLabel=source.label,
            engineMode="mediapipe",
        )
        annotated = self._annotate_mediapipe_frame(frame.copy(), payload, landmarks)
        return payload, annotated

    def _record_calibration_sample(self, has_face: bool, features: dict, source: VideoSource, now: float) -> str:
        session = self._calibration_session
        if not session or session.get("sourceId") != source.source_id:
            return ""

        elapsed = now - float(session["startedAt"])
        if has_face and self._is_calibration_sample_reliable(features):
            session["samples"].append({
                "yaw": features.get("headYaw"),
                "pitch": features.get("headPitch"),
                "roll": features.get("headRoll"),
                "faceCenterX": features.get("faceCenterX"),
                "faceCenterY": features.get("faceCenterY"),
                "faceBoxArea": features.get("faceBoxArea"),
                "eyeOpenRatio": features.get("eyeOpenRatio"),
                "motionStability": features.get("motionStability"),
            })

        if elapsed < float(session["duration"]):
            remaining = max(int(round(float(session["duration"]) - elapsed)), 0)
            return f"Calibration collecting: keep normal study posture for {remaining}s."

        return self._finish_calibration(source)

    def _is_calibration_sample_reliable(self, features: dict) -> bool:
        required = ["headYaw", "headPitch", "headRoll", "faceCenterX", "faceCenterY", "faceBoxArea", "eyeOpenRatio"]
        if not features.get("faceVisible", False):
            return False
        if any(features.get(key) is None for key in required):
            return False
        if not features.get("frameReliable", False):
            return False
        return float(features.get("motionStability", 0.0)) >= 0.35

    def _finish_calibration(self, source: VideoSource) -> str:
        session = self._calibration_session
        self._calibration_session = None
        samples = list(session.get("samples", [])) if session else []
        if len(samples) < max(10, int(self.config.analysis_fps * 2)):
            return "Calibration failed: not enough stable face samples. Please keep the study posture and try again."

        def sample_median(key: str) -> float:
            return round(float(median(float(sample[key]) for sample in samples if sample.get(key) is not None)), 4)

        payload = {
            "sourceId": source.source_id,
            "sourceLabel": source.label,
            "profileName": self._safe_source_key(source.source_id),
            "createdAt": int(time.time() * 1000),
            "sampleCount": len(samples),
            "baseline": {
                "yawMedian": sample_median("yaw"),
                "pitchMedian": sample_median("pitch"),
                "rollMedian": sample_median("roll"),
                "faceCenterX": sample_median("faceCenterX"),
                "faceCenterY": sample_median("faceCenterY"),
                "faceBoxArea": sample_median("faceBoxArea"),
                "eyeOpenMedian": sample_median("eyeOpenRatio"),
            },
            "screen": {},
            "thresholds": {
                "yawSoftDelta": 12,
                "yawHardDelta": 25,
                "pitchSoftDelta": 15,
                "pitchHardDelta": 30,
                "rollHardDelta": 22,
                "centerHardDelta": 0.24,
                "areaMinRatio": 0.55,
                "areaMaxRatio": 1.8,
                "eyeClosedRatio": 0.55,
            },
        }
        payload["screen"] = dict(payload["baseline"])
        calibration_path = self._calibration_path(source.source_id)
        calibration_path.parent.mkdir(parents=True, exist_ok=True)
        calibration_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._focus_analyzer = self._create_focus_analyzer()
        self._presence_history.clear()
        self._away_started_at = None
        return f"Calibration saved for {source.label}: {len(samples)} stable samples."

    def _map_mediapipe_status(self, state: dict, away_seconds: int) -> str:
        if away_seconds >= self.config.away_timeout_seconds:
            return "timeout_away"
        mp_status = str(state.get("status", "uncertain"))
        score = float(state.get("score", 0))
        if mp_status == "away":
            return "away"
        if mp_status == "focused":
            return "flow" if score >= 86 else "normal"
        if mp_status == "distracted" or mp_status == "fatigue":
            return "distracted"
        return "normal" if score >= 68 else "distracted"

    def _metrics_from_mediapipe_state(self, state: dict, features: dict) -> FocusMetrics:
        subs = state.get("subScores", {}) or {}
        head = float(subs.get("headOrientation", 0.0))
        eye = float(subs.get("eyeState", 0.5 if features.get("eyeReliable", False) is False else 0.0))
        gaze = self._clamp((head * 0.7 + eye * 0.3) * 100)
        posture = self._clamp(float(subs.get("taskPosture", 0.0)) * 100)
        stability = self._clamp(float(subs.get("motionStability", features.get("motionStability", 0.0))) * 100)
        presence = self._clamp(float(state.get("recentFaceRatio", subs.get("presence", 0.0))) * 100)
        return FocusMetrics(gaze=gaze, posture=posture, stability=stability, presence=presence)

    def _compose_mediapipe_event(self, status: str, state: dict, features: dict) -> str:
        if status == "timeout_away":
            return "Away-from-seat timeout exceeded."
        if status == "away":
            return "Temporary away-from-seat state detected."
        if features.get("eyesClosed", False) or state.get("status") == "fatigue":
            return "Attention drift is rising. A light reminder may help."
        if status == "flow":
            return "Strong sustained attention detected."
        if status == "distracted":
            return "Attention drift is rising. A light reminder may help."
        return "Study rhythm is steady."

    def _annotate_mediapipe_frame(self, frame: object, payload: FocusPayload, landmarks) -> object:
        assert cv2 is not None
        if landmarks is not None:
            height, width = frame.shape[:2]
            for index, landmark in enumerate(landmarks):
                if index % 2 != 0:
                    continue
                px = int(landmark.x * width)
                py = int(landmark.y * height)
                if 0 <= px < width and 0 <= py < height:
                    cv2.circle(frame, (px, py), 1, (100, 200, 120), -1)

        if payload.status == "timeout_away":
            frame = self._annotate_frame(frame, payload, None)
        return frame

    def _read_source_frame(self, source: VideoSource) -> object | None:
        assert cv2 is not None
        if time.time() < self._source_retry_after:
            return None

        source_signature = f"{source.source_id}:{source.location}:{source.transport}"
        if self._capture_signature != source_signature:
            self._reset_capture()
            self._capture_signature = source_signature
            self._last_source_error = "正在连接新的视频源。"

        if source.transport == "snapshot":
            return self._read_snapshot_frame(source.location)
        return self._read_stream_frame(source)

    def _read_stream_frame(self, source: VideoSource) -> object | None:
        assert cv2 is not None
        if self._capture is None:
            location = self._parse_location(source.location, source.source_type)
            self._capture = self._open_capture(location, source.source_type)
            if self._capture is not None:
                self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
                self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)

        if not self._capture or not self._capture.isOpened():
            self._last_source_error = f"无法打开视频源：{source.location}"
            self._release_capture()
            self._defer_source_retry()
            return None

        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._last_source_error = f"已经连接到视频源，但读取画面失败：{source.location}"
            self._release_capture()
            self._defer_source_retry()
            return None
        return frame

    def _read_snapshot_frame(self, url: str) -> object | None:
        assert cv2 is not None
        assert np is not None
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=3) as response:
                payload = response.read()
        except Exception as error:  # pragma: no cover
            self._last_source_error = f"截图地址请求失败：{error}"
            self._defer_source_retry()
            return None

        array = np.frombuffer(payload, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            self._last_source_error = "截图内容返回成功，但图像解码失败。"
            self._defer_source_retry()
        return frame

    def _probe_source_frame(self, source: VideoSource) -> tuple[bool, str]:
        if self.config.mock_mode:
            return False, "视觉节点处于演示模式，未连接真实视频流。"
        if cv2 is None or np is None:
            return False, "OpenCV 或图像解码依赖不可用，无法检测视频流。"

        if source.transport == "snapshot":
            frame = self._read_snapshot_frame(source.location)
            if frame is None:
                return False, self._last_source_error or "截图地址没有返回可用画面。"
            return True, "已检测到可用截图画面。"

        location = self._parse_location(source.location, source.source_type)
        capture = self._open_capture(location, source.source_type)
        try:
            if capture is not None:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)

            if not capture or not capture.isOpened():
                return False, f"无法打开视频源：{source.location}"

            for _ in range(4):
                ok, frame = capture.read()
                if ok and frame is not None:
                    return True, "已检测到可用视频流。"
                time.sleep(0.06)
            return False, f"已经连接到视频源，但读取画面失败：{source.location}"
        finally:
            if capture is not None:
                capture.release()

    def _open_capture(self, location: int | str, source_type: str):
        if cv2 is None:
            return None
        if source_type == "local_camera" and isinstance(location, int):
            return self._open_local_capture(location)
        capture = cv2.VideoCapture()
        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.config.stream_open_timeout_ms)
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.config.stream_read_timeout_ms)
        capture.open(location)
        return capture

    def _open_local_capture(self, index: int):
        assert cv2 is not None
        for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
            capture = cv2.VideoCapture(index, backend)
            if capture and capture.isOpened():
                return capture
            if capture:
                capture.release()
        return None

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _reset_capture(self) -> None:
        self._release_capture()
        self._capture_signature = ""
        self._prev_gray = None

    def _defer_source_retry(self) -> None:
        self._source_retry_after = time.time() + self.config.source_retry_seconds

    def _parse_location(self, location: str, source_type: str) -> int | str:
        if source_type == "local_camera" and location.isdigit():
            return int(location)
        return location

    def _compute_away_seconds(self, detected: bool, now: float) -> int:
        if detected:
            self._away_started_at = None
            return 0
        if self._away_started_at is None:
            self._away_started_at = now
        return max(int(now - self._away_started_at), 0)

    def _presence_score(self) -> int:
        if not self._presence_history:
            return 0
        visible = sum(1 for _, detected in self._presence_history if detected)
        return int(round(visible / len(self._presence_history) * 100))

    def _estimate_gaze(self, gray: object, face_box: tuple[int, int, int, int]) -> int:
        assert cv2 is not None
        x, y, w, h = [int(v) for v in face_box]
        face_roi = gray[y : y + h, x : x + w]
        face_center_x = x + w / 2
        frame_center_x = gray.shape[1] / 2
        horizontal_offset = abs(face_center_x - frame_center_x) / max(frame_center_x, 1)

        eye_bonus = 0
        if self._eye_cascade is not None and not self._eye_cascade.empty():
            eyes = self._eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=4, minSize=(16, 16))
            eye_bonus = min(len(eyes), 2) * 12

        score = 100 - horizontal_offset * 85 + eye_bonus
        return self._clamp(score)

    def _estimate_posture(self, face_box: tuple[int, int, int, int], frame_width: int, frame_height: int) -> int:
        x, y, w, h = [int(v) for v in face_box]
        face_center_x = x + w / 2
        face_center_y = y + h / 2
        frame_center_x = frame_width / 2
        expected_y = frame_height * 0.36

        horizontal_penalty = abs(face_center_x - frame_center_x) / max(frame_center_x, 1) * 36
        vertical_penalty = abs(face_center_y - expected_y) / max(frame_height, 1) * 120
        size_ratio = h / max(frame_height, 1)
        size_penalty = 0
        if size_ratio < 0.18:
            size_penalty += (0.18 - size_ratio) * 180
        if size_ratio > 0.46:
            size_penalty += (size_ratio - 0.46) * 180

        score = 100 - horizontal_penalty - vertical_penalty - size_penalty
        return self._clamp(score)

    def _estimate_motion(self, gray: object, face_box: tuple[int, int, int, int] | None) -> int:
        assert cv2 is not None
        if self._prev_gray is None:
            return 88

        region = gray
        prev_region = self._prev_gray
        if face_box is not None:
            x, y, w, h = [int(v) for v in face_box]
            pad = int(max(w, h) * 0.35)
            x0 = max(x - pad, 0)
            y0 = max(y - pad, 0)
            x1 = min(x + w + pad, gray.shape[1])
            y1 = min(y + h + pad, gray.shape[0])
            region = gray[y0:y1, x0:x1]
            prev_region = self._prev_gray[y0:y1, x0:x1]

        if region.size == 0 or prev_region.size == 0:
            return 80

        diff = cv2.absdiff(region, prev_region)
        motion_value = float(diff.mean())
        self._motion_history.append(motion_value)
        motion_avg = sum(self._motion_history) / len(self._motion_history)
        score = 100 - motion_avg * 2.8
        return self._clamp(score)

    def _resolve_status(self, focus_score: int, gaze_score: int, away_seconds: int) -> str:
        if away_seconds >= self.config.away_timeout_seconds:
            return "timeout_away"
        if away_seconds >= 8:
            return "away"
        if focus_score >= 86 and gaze_score >= 78:
            return "flow"
        if focus_score >= 68:
            return "normal"
        return "distracted"

    def _compose_simple_event(
        self,
        face_box: tuple[int, int, int, int],
        gaze_score: int,
        posture_score: int,
        stability_score: int,
    ) -> str:
        x, y, w, h = [int(v) for v in face_box]
        if gaze_score < 52:
            return "人脸明显偏离学习区域中心，可能出现分心。"
        if posture_score < 55:
            return "人脸位置显示坐姿可能前倾或偏离。"
        if stability_score < 58:
            return "头部和上半身附近检测到较大幅度动作。"
        if h < 90:
            return "孩子距离摄像头较远，但仍能确认在座。"
        return "已在当前学习区域内检测并跟踪到人脸。"

    def _annotate_frame(
        self,
        frame: object,
        payload: FocusPayload,
        face_box: tuple[int, int, int, int] | None,
    ) -> object:
        assert cv2 is not None
        if face_box is not None:
            x, y, w, h = [int(v) for v in face_box]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (126, 198, 151), 2)
            cx = x + w // 2
            cy = y + h // 2
            cv2.circle(frame, (cx, cy), 4, (126, 198, 151), -1)

        if payload.status == "timeout_away":
            mask = frame.copy()
            height, width = frame.shape[:2]
            cv2.rectangle(mask, (0, 0), (width, height), (60, 60, 170), -1)
            cv2.addWeighted(mask, 0.28, frame, 0.72, 0, frame)
            self._put_text(frame, "AWAY TIMEOUT", (46, height // 2 - 12), 1.0, (255, 255, 255), 3)
            self._put_text(
                frame,
                f"{max(payload.awaySeconds - self.config.away_timeout_seconds, 0)}s",
                (46, height // 2 + 26),
                0.8,
                (255, 255, 255),
                2,
            )
        return frame

    def _render_mock_frame(self, payload: FocusPayload, source: VideoSource) -> object | None:
        if cv2 is None or np is None:  # pragma: no cover
            return None

        frame = np.zeros((self.config.frame_height, self.config.frame_width, 3), dtype=np.uint8)
        frame[:] = (238, 241, 236)
        cv2.circle(frame, (int(self.config.frame_width * 0.78), 120), 110, (214, 232, 216), -1)
        cv2.circle(frame, (135, self.config.frame_height - 95), 130, (226, 213, 194), -1)
        cv2.rectangle(
            frame,
            (int(self.config.frame_width * 0.38), int(self.config.frame_height * 0.2)),
            (int(self.config.frame_width * 0.66), int(self.config.frame_height * 0.72)),
            (126, 198, 151),
            2,
        )

        if payload.status in {"away", "timeout_away"}:
            self._put_text(frame, "AWAY", (42, 62), 0.9, (127, 88, 58), 2)

        if payload.status == "timeout_away":
            mask = frame.copy()
            cv2.rectangle(mask, (0, 0), (self.config.frame_width, self.config.frame_height), (56, 72, 180), -1)
            cv2.addWeighted(mask, 0.16, frame, 0.84, 0, frame)
            self._put_text(frame, "AWAY TIMEOUT", (self.config.frame_width // 2 - 170, 120), 1.0, (255, 255, 255), 3)
        return frame

    def _encode_frame(self, frame: object | None) -> bytes:
        if frame is None or cv2 is None:
            return PLACEHOLDER_JPEG
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.config.jpeg_quality])
        if not ok:
            return PLACEHOLDER_JPEG
        return encoded.tobytes()

    def _put_text(
        self,
        frame: object,
        text: str,
        origin: tuple[int, int],
        scale: float,
        color: tuple[int, int, int],
        thickness: int,
    ) -> None:
        assert cv2 is not None
        cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

    def _draw_bar(
        self,
        frame: object,
        label: str,
        score: int,
        color: tuple[int, int, int],
        x: int,
        y: int,
        bar_width: int = 210,
        bar_height: int = 14,
    ) -> None:
        assert cv2 is not None
        self._put_text(frame, label, (x, y), 0.56, (75, 86, 79), 1)
        top = y + 8
        cv2.rectangle(frame, (x + 92, top), (x + 92 + bar_width, top + bar_height), (228, 232, 228), -1)
        fill_width = int(bar_width * score / 100)
        cv2.rectangle(frame, (x + 92, top), (x + 92 + fill_width, top + bar_height), color, -1)
        self._put_text(frame, str(score), (x + 92 + bar_width + 12, y + 11), 0.52, (75, 86, 79), 1)

    def _clamp(self, value: float, lower: int = 0, upper: int = 100) -> int:
        return int(max(lower, min(upper, round(value))))

    def _why_mock_mode(self) -> str:
        if self.config.mock_mode:
            return "Mock mode is forced by FOCUS_FORCE_MOCK."
        if cv2 is None or np is None:
            return "OpenCV or numpy is unavailable."
        if self._face_cascade is None or self._face_cascade.empty():
            return "OpenCV face cascade is unavailable."
        return "Camera analysis is unavailable."

    def _make_network_source_id(self, label: str) -> str:
        base = "".join(char.lower() if char.isalnum() else "-" for char in label).strip("-") or "network"
        source_id = f"network-{base}"
        suffix = 2
        while source_id in self._sources:
            source_id = f"network-{base}-{suffix}"
            suffix += 1
        return source_id
