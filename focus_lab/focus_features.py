"""
Focus feature extraction and scoring from MediaPipe Face Landmarker results.
v2 — sub-scores, state machine, calibration, matrix-based head pose.
"""
from __future__ import annotations
import math
import json
import os
import time
from typing import Optional
import numpy as np
import cv2

# ── Landmark constants (MediaPipe 478 topology) ─────────────────
LEFT_EYE  = [33, 133, 157, 158, 159, 160, 161, 173]
RIGHT_EYE = [362, 263, 384, 385, 386, 387, 388, 398]
LEFT_IRIS  = 468
RIGHT_IRIS = 473
NOSE_TIP = 1
FACE_OVAL_TOP    = 10
FACE_OVAL_BOTTOM = 152
FACE_LEFT        = 234
FACE_RIGHT       = 454

# ── Calibration ─────────────────────────────────────────────────
class Calibration:
    """Personal baseline from calibrate.py. Loaded from focus_lab/config/calibration.json."""

    def __init__(self, path: str | None = None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "config", "calibration.json")
        self.data: dict = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    @property
    def baseline(self) -> dict:
        return self.data.get("baseline") or self.data.get("screen", {})

    @property
    def has_calibration(self) -> bool:
        return bool(self.data)

    @property
    def screen_yaw(self) -> float:
        return float(self.baseline.get("yawMedian", 0.0))

    @property
    def screen_pitch(self) -> float:
        return float(self.baseline.get("pitchMedian", 0.0))

    @property
    def screen_roll(self) -> float:
        return float(self.baseline.get("rollMedian", 0.0))

    @property
    def screen_eye_open(self) -> float:
        return float(self.baseline.get("eyeOpenMedian", self.baseline.get("eyeOpenRatio", 0.25)))

    @property
    def face_center_x(self) -> float:
        return float(self.baseline.get("faceCenterX", 0.5))

    @property
    def face_center_y(self) -> float:
        return float(self.baseline.get("faceCenterY", 0.4))

    @property
    def face_box_area(self) -> float:
        return float(self.baseline.get("faceBoxArea", self.baseline.get("faceBoxAreaMedian", 0.12)))

    @property
    def writing_pitch(self) -> float:
        return float(self.data.get("writing", {}).get("pitchMedian", -18.0))

    @property
    def yaw_soft_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("yawSoftDelta", 15.0))

    @property
    def yaw_safe_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("yawSafeDelta", self.yaw_soft_delta))

    @property
    def yaw_hard_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("yawHardDelta", 25.0))

    @property
    def pitch_safe_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("pitchSafeDelta", self.data.get("thresholds", {}).get("pitchSoftDelta", 12.0)))

    @property
    def pitch_writing_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("pitchWritingDelta", 25.0))

    @property
    def pitch_hard_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("pitchHardDelta", 30.0))

    @property
    def roll_safe_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("rollSafeDelta", 8.0))

    @property
    def roll_hard_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("rollHardDelta", 22.0))

    @property
    def center_safe_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("centerSafeDelta", 0.08))

    @property
    def center_hard_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("centerHardDelta", 0.24))

    @property
    def area_min_ratio(self) -> float:
        return float(self.data.get("thresholds", {}).get("areaMinRatio", 0.55))

    @property
    def area_max_ratio(self) -> float:
        return float(self.data.get("thresholds", {}).get("areaMaxRatio", 1.8))

    @property
    def area_hard_min_ratio(self) -> float:
        return float(self.data.get("thresholds", {}).get("areaHardMinRatio", 0.35))

    @property
    def area_hard_max_ratio(self) -> float:
        return float(self.data.get("thresholds", {}).get("areaHardMaxRatio", 2.6))

    @property
    def eye_closed_ratio(self) -> float:
        return float(self.data.get("thresholds", {}).get("eyeClosedRatio", 0.55))


_calibration: Calibration | None = None

def get_calibration() -> Calibration:
    global _calibration
    if _calibration is None:
        _calibration = Calibration()
    return _calibration

def reload_calibration(path: str | None = None):
    global _calibration
    _calibration = Calibration(path)


# ── Conversions ─────────────────────────────────────────────────
def landmark_to_ndarray(landmarks) -> np.ndarray:
    return np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float64)


# ── Head pose ───────────────────────────────────────────────────
def _decompose_rotation_matrix(rmat: np.ndarray) -> tuple[float, float, float]:
    """Decompose 3x3 rotation matrix to yaw, pitch, roll in degrees."""
    sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        yaw   = math.atan2(rmat[1, 0], rmat[0, 0]) * 180 / math.pi
        pitch = math.atan2(-rmat[2, 0], sy) * 180 / math.pi
        roll  = math.atan2(rmat[2, 1], rmat[2, 2]) * 180 / math.pi
    else:
        yaw   = math.atan2(-rmat[0, 1], rmat[1, 1]) * 180 / math.pi
        pitch = math.atan2(-rmat[2, 0], sy) * 180 / math.pi
        roll  = 0.0
    return float(yaw), float(pitch), float(roll)


def estimate_head_pose_from_matrix(transform_matrix) -> dict | None:
    """Extract yaw/pitch/roll from MediaPipe facial_transformation_matrixes.

    The matrix is 4x4 row-major: [r11 r12 r13 tx, r21 r22 r23 ty, r31 r32 r33 tz, 0 0 0 1].
    We extract the 3x3 rotation and decompose.
    """
    if transform_matrix is None:
        return None
    try:
        m = np.array(transform_matrix, dtype=np.float64).reshape(4, 4)
        rmat = m[:3, :3]
        yaw, pitch, roll = _decompose_rotation_matrix(rmat)
        return {"yaw": round(yaw, 1), "pitch": round(pitch, 1), "roll": round(roll, 1)}
    except Exception:
        return None


def estimate_head_pose_pnp(landmarks_3d: np.ndarray, image_shape: tuple[int, int]) -> dict | None:
    """Fallback: solvePnP with generic 3D face model."""
    h, w = image_shape[:2]
    indices_2d = [NOSE_TIP, FACE_OVAL_BOTTOM, LEFT_EYE[0], RIGHT_EYE[0], 61, 291]
    pts_2d = np.array([[landmarks_3d[i][0] * w, landmarks_3d[i][1] * h] for i in indices_2d], dtype=np.float64)
    pts_3d = np.array([
        [ 0.0,  0.0,  0.0], [ 0.0, -0.3, -0.5],
        [-0.22, 0.18, 0.10], [ 0.22, 0.18, 0.10],
        [-0.25, -0.1, 0.05], [ 0.25, -0.1, 0.05],
    ], dtype=np.float64)
    focal = float(w)
    camera_matrix = np.array([[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]], dtype=np.float64)
    try:
        ok, rvec, _ = cv2.solvePnP(pts_3d, pts_2d, camera_matrix, None, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            return None
        rmat, _ = cv2.Rodrigues(rvec)
        yaw, pitch, roll = _decompose_rotation_matrix(rmat)
        return {"yaw": round(yaw, 1), "pitch": round(pitch, 1), "roll": round(roll, 1)}
    except Exception:
        return None


def estimate_head_pose(landmarks_3d: np.ndarray, image_shape: tuple[int, int],
                       transform_matrix=None) -> dict:
    """Head pose: prefer transformation matrix, fallback to solvePnP."""
    if transform_matrix is not None:
        result = estimate_head_pose_from_matrix(transform_matrix)
        if result is not None:
            return result
    result = estimate_head_pose_pnp(landmarks_3d, image_shape)
    if result is not None:
        return result
    return {"yaw": None, "pitch": None, "roll": None, "source": "none"}


# ── Eye features ────────────────────────────────────────────────
def eye_aspect_ratio(landmarks_3d: np.ndarray, eye_indices: list[int]) -> float:
    pts = landmarks_3d[eye_indices]
    h_dist = np.linalg.norm(pts[0] - pts[1])
    if h_dist < 1e-6:
        return 0.0
    v_upper = (pts[2] + pts[3]) / 2
    v_lower = (pts[4] + pts[5]) / 2
    v_dist = np.linalg.norm(v_upper - v_lower)
    return float(v_dist / h_dist)


def compute_eye_features(landmarks_3d: np.ndarray, cal: Calibration) -> dict:
    """Left/right eye open ratios, reliability, and closed detection."""
    left_ear  = eye_aspect_ratio(landmarks_3d, LEFT_EYE)
    right_ear = eye_aspect_ratio(landmarks_3d, RIGHT_EYE)
    avg_ear   = (left_ear + right_ear) / 2

    # Reliability: if one eye is very different from baseline, flag as unreliable
    baseline = cal.screen_eye_open if cal.has_calibration else 0.25
    left_dev  = abs(left_ear - baseline) / max(baseline, 0.01)
    right_dev = abs(right_ear - baseline) / max(baseline, 0.01)
    eye_reliable = (left_dev < 0.6 and right_dev < 0.6)

    # Closed detection: relative to personal baseline
    closed_threshold = baseline * cal.eye_closed_ratio if cal.has_calibration else 0.12
    left_closed  = left_ear < closed_threshold
    right_closed = right_ear < closed_threshold

    return {
        "leftEyeOpenRatio":  round(float(left_ear), 4),
        "rightEyeOpenRatio": round(float(right_ear), 4),
        "eyeOpenRatio":      round(float(avg_ear), 4),
        "eyeReliable":       eye_reliable,
        "eyesClosed":        left_closed and right_closed,
    }


# ── Face quality ────────────────────────────────────────────────
def compute_face_quality(landmarks_3d: np.ndarray, image_shape: tuple[int, int]) -> dict:
    """Bounding box area, center position, and landmark quality heuristic."""
    h, w = image_shape[:2]
    xs = landmarks_3d[:, 0]
    ys = landmarks_3d[:, 1]
    x_min, x_max = float(xs.min()), float(xs.max())
    y_min, y_max = float(ys.min()), float(ys.max())
    box_w = x_max - x_min
    box_h = y_max - y_min
    box_area = box_w * box_h
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2

    # Frame reliable heuristic
    frame_reliable = True
    reasons = []
    if box_area < 0.03:
        frame_reliable = False
        reasons.append("face_too_small")
    if center_x < 0.15 or center_x > 0.85:
        frame_reliable = False
        reasons.append("face_too_edge")
    if center_y < 0.08 or center_y > 0.92:
        frame_reliable = False
        reasons.append("face_too_edge")

    return {
        "faceBoxArea":      round(float(box_area), 4),
        "faceCenterX":      round(float(center_x), 3),
        "faceCenterY":      round(float(center_y), 3),
        "landmarkQuality":  1.0,  # placeholder; future: check landmark z-variance
        "frameReliable":    frame_reliable,
        "frameReliabilityReasons": reasons,
    }


# ── Motion stability ────────────────────────────────────────────
def compute_motion_stability(nose_history: list[np.ndarray], current_nose: np.ndarray,
                             frame_width: int) -> float:
    """Stability from recent nose position displacements."""
    if len(nose_history) < 2:
        return 0.5
    recent = nose_history[-5:] if len(nose_history) >= 5 else nose_history
    displacements = [np.linalg.norm(current_nose - p) for p in recent]
    avg_disp_px = float(np.mean(displacements)) * frame_width
    return round(float(max(0.0, 1.0 - avg_disp_px / 18.0)), 4)


# ── Main feature extraction ─────────────────────────────────────
def compute_features(landmarks_3d: np.ndarray, image_shape: tuple[int, int],
                     transform_matrix=None, cal: Calibration | None = None,
                     nose_history: list | None = None) -> dict:
    """Compute all features from a single frame's landmarks."""
    if cal is None:
        cal = get_calibration()
    h, w = image_shape[:2]
    nose_xy = np.array([float(landmarks_3d[NOSE_TIP][0]), float(landmarks_3d[NOSE_TIP][1])])

    # Head pose
    pose = estimate_head_pose(landmarks_3d, image_shape, transform_matrix)

    # Eyes
    eye = compute_eye_features(landmarks_3d, cal)

    # Face quality
    quality = compute_face_quality(landmarks_3d, image_shape)

    # Motion stability (uses caller-provided nose_history)
    motion = compute_motion_stability(nose_history or [], nose_xy, w)

    # Activity detection
    yaw = pose.get("yaw")
    pitch = pose.get("pitch")
    activity = "unknown"
    if yaw is not None and pitch is not None:
        yaw_delta = abs(yaw - cal.screen_yaw) if cal.has_calibration else abs(yaw)
        pitch_delta = abs(pitch - cal.writing_pitch) if cal.has_calibration else abs(pitch)
        if yaw_delta < cal.yaw_soft_delta and pitch_delta < cal.pitch_writing_delta:
            activity = "writing"
        elif yaw_delta < cal.yaw_soft_delta:
            activity = "screen_or_writing"

    return {
        "faceVisible":    True,
        "headYaw":        pose.get("yaw"),
        "headPitch":      pose.get("pitch"),
        "headRoll":       pose.get("roll"),
        "headPoseSource": pose.get("source", "pnp"),
        "leftEyeOpenRatio":  eye["leftEyeOpenRatio"],
        "rightEyeOpenRatio": eye["rightEyeOpenRatio"],
        "eyeOpenRatio":      eye["eyeOpenRatio"],
        "eyeReliable":       eye["eyeReliable"],
        "eyesClosed":        eye["eyesClosed"],
        "faceBoxArea":    quality["faceBoxArea"],
        "faceCenterX":    quality["faceCenterX"],
        "faceCenterY":    quality["faceCenterY"],
        "landmarkQuality": quality["landmarkQuality"],
        "frameReliable":  quality["frameReliable"],
        "motionStability": motion,
        "activity": activity,
    }


def no_face_features() -> dict:
    return {
        "faceVisible":    False,
        "headYaw":        None, "headPitch": None, "headRoll": None, "headPoseSource": None,
        "leftEyeOpenRatio": None, "rightEyeOpenRatio": None,
        "eyeOpenRatio":   None, "eyeReliable": False, "eyesClosed": False,
        "faceBoxArea":    0.0,  "faceCenterX": None, "faceCenterY": None,
        "landmarkQuality": 0.0, "frameReliable": False,
        "motionStability": 0.0, "activity": "away",
    }


# ── Sub-scores (0-1 scale) ──────────────────────────────────────
def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def safe_quadratic_score(delta: float, safe_delta: float, hard_delta: float) -> float:
    """Return 1 inside the safe band, then fall quadratically to 0."""
    if delta <= safe_delta:
        return 1.0
    span = max(hard_delta - safe_delta, 1e-6)
    t = clamp01((delta - safe_delta) / span)
    return clamp01(1.0 - t * t)


def band_quadratic_score(value: float, safe_min: float, safe_max: float,
                         hard_min: float, hard_max: float) -> float:
    """Score a value with a no-penalty band and steeper outer penalties."""
    if safe_min <= value <= safe_max:
        return 1.0
    if value < safe_min:
        span = max(safe_min - hard_min, 1e-6)
        t = clamp01((safe_min - value) / span)
    else:
        span = max(hard_max - safe_max, 1e-6)
        t = clamp01((value - safe_max) / span)
    return clamp01(1.0 - t * t)


def compute_sub_scores(features: dict, recent_face_ratio: float,
                       cal: Calibration, yaw_history: list[float],
                       eyes_closed_count: int) -> dict:
    """Compute independent 0-1 sub-scores."""
    yaw = features.get("headYaw")
    pitch = features.get("headPitch")
    ear = features.get("eyeOpenRatio") or 0.0
    eye_reliable = features.get("eyeReliable", False)
    stability = features.get("motionStability", 0.5)
    activity = features.get("activity", "unknown")

    # 1. Presence score
    presence_score = clamp01(recent_face_ratio)

    # 2. Head orientation: yaw relative to calibrated baseline
    if yaw is not None and cal.has_calibration:
        yaw_delta = abs(yaw - cal.screen_yaw)
    elif yaw is not None:
        yaw_delta = abs(yaw)
    else:
        yaw_delta = 90
    # yaw_delta 0°→1.0, 10°→0.33, 15°→0, steep drop
    head_ori = clamp01(1.0 - yaw_delta / 15.0)

    # 3. Eye state
    if eye_reliable and ear > 0.0:
        baseline = cal.screen_eye_open if cal.has_calibration else 0.25
        eye_state = clamp01(min(ear / max(baseline * 0.7, 0.01), 1.0))
        if eyes_closed_count > 10:
            eye_state *= 0.5
    else:
        eye_state = 0.5  # neutral when eyes unreliable

    # 4. Motion stability
    motion = stability  # already 0-1

    # 5. Task posture: accepts both screen and writing poses
    if activity == "writing" or activity == "screen_or_writing":
        task_posture = 0.85
    elif yaw_delta < 10:
        task_posture = 1.0
    elif yaw_delta < 20:
        task_posture = 0.5
    else:
        task_posture = 0.15

    return {
        "presence":         round(float(presence_score), 4),
        "headOrientation":  round(float(head_ori), 4),
        "eyeState":         round(float(eye_state), 4),
        "motionStability":  round(float(motion), 4),
        "taskPosture":      round(float(task_posture), 4),
    }


def weighted_score(subs: dict, yaw_history: list[float], features: dict) -> float:
    """Weighted combination of sub-scores → 0-100."""
    # Dynamic weights: if large yaw sustained, reduce headOrientation weight
    large_yaw_count = sum(1 for y in yaw_history[-10:] if y > 25) if yaw_history else 0
    w_head  = max(0.08, 0.35 - large_yaw_count * 0.015)
    w_eye   = 0.15 if features.get("eyeReliable", False) else 0.05
    w_extra = (0.35 - w_head) + (0.15 - w_eye)
    # w_extra redistributes reduced head/eye weight to taskPosture

    raw = (
        0.25 * subs["presence"] +
        w_head * subs["headOrientation"] +
        w_eye * subs["eyeState"] +
        0.10 * subs["motionStability"] +
        (0.15 + w_extra) * subs["taskPosture"]
    )
    return clamp01(raw) * 100.0


def build_reason_codes(subs: dict, features: dict, recent_face_ratio: float) -> list[str]:
    codes = []
    if features.get("faceVisible", False):
        codes.append("face_visible")
    else:
        codes.append("face_not_visible")
    if subs.get("headOrientation", 0) > 0.5:
        codes.append("head_stable")
    elif subs.get("headOrientation", 0) > 0.3:
        codes.append("head_moderate")
    else:
        codes.append("head_turned")
    if features.get("eyesClosed", False):
        codes.append("eyes_closed")
    elif features.get("eyeReliable", False):
        codes.append("eyes_open")
    if subs.get("motionStability", 0) > 0.6:
        codes.append("motion_stable")
    elif subs.get("motionStability", 0) > 0.3:
        codes.append("motion_moderate")
    else:
        codes.append("motion_unstable")
    if features.get("activity") == "writing":
        codes.append("activity_writing")
    elif features.get("activity") == "screen_or_writing":
        codes.append("activity_screen_or_writing")
    if recent_face_ratio < 0.5:
        codes.append("presence_low")
    return codes


# ── State Machine ───────────────────────────────────────────────
class StateMachine:
    """Replaces direct score→status mapping with transition durations."""

    STATES = ["focused", "uncertain", "distracted", "away", "fatigue"]

    def __init__(self):
        self.current: str = "uncertain"
        self._pending: str | None = None
        self._pending_start_s: float = 0.0
        self._status_start_s: float = time.monotonic()
        self._prev_timestamp_s: float = 0.0

    def update(self, score: float, recent_face_ratio: float,
               presence: bool, eyes_closed: bool, now_s: float) -> dict:
        """Evaluate transitions and return current state with metadata."""
        if self._prev_timestamp_s == 0.0:
            self._prev_timestamp_s = now_s
            self._status_start_s = now_s

        # Rule 1: Away detection (highest priority)
        if recent_face_ratio < 0.25 or not presence:
            self._maybe_transition("away", 0.6, now_s)
            self._pending = None
            return self._result(now_s)

        # Rule 2: Fatigue detection
        if eyes_closed and presence:
            self._maybe_transition("fatigue", 1.0, now_s)
            if self.current == "fatigue":
                return self._result(now_s)

        # Rule 3: Standard transitions
        if self.current == "away":
            self._maybe_transition("uncertain", 0.8, now_s)

        elif self.current == "focused":
            self._maybe_transition("uncertain", 0.6, now_s,
                                   condition=(score < 75))

        elif self.current == "uncertain":
            if score > 80:
                self._maybe_transition("focused", 1.5, now_s)
            elif score < 55:
                self._maybe_transition("distracted", 1.0, now_s)
            else:
                self._cancel_pending()

        elif self.current == "distracted":
            self._maybe_transition("focused", 1.5, now_s,
                                   condition=(score > 80))

        elif self.current == "fatigue":
            if not eyes_closed:
                self._maybe_transition("uncertain", 0.8, now_s)

        return self._result(now_s)

    def _maybe_transition(self, target: str, duration_s: float, now_s: float,
                          condition: bool = True):
        if not condition:
            self._cancel_pending()
            return
        if self.current == target:
            return
        if self._pending == target:
            if now_s - self._pending_start_s >= duration_s:
                self.current = target
                self._status_start_s = now_s
                self._pending = None
        else:
            self._pending = target
            self._pending_start_s = now_s

    def _cancel_pending(self):
        self._pending = None

    def _result(self, now_s: float) -> dict:
        status_duration_ms = int((now_s - self._status_start_s) * 1000)
        pending_duration_ms = int((now_s - self._pending_start_s) * 1000) if self._pending else 0
        return {
            "status": self.current,
            "statusDurationMs": status_duration_ms,
            "pendingStatus": self._pending,
            "pendingDurationMs": pending_duration_ms,
        }


# ── FocusAnalyzer (updated) ─────────────────────────────────────
class FocusAnalyzer:
    """Stateful analyzer with sliding windows, sub-scores, state machine."""

    def __init__(self, window_seconds: float = 2.0, fps_estimate: int = 15,
                 calibration_path: str | None = None):
        self.window_frames = max(1, int(window_seconds * fps_estimate))
        self.cal = Calibration(calibration_path)
        self.face_history: list[bool] = []
        self.yaw_history: list[float] = []
        self.ear_history: list[float] = []
        self.nose_history: list[np.ndarray] = []
        self.score_history: list[float] = []
        self.smoothed_score: float = 50.0
        self.sm = StateMachine()

    def update(self, has_face: bool, features: dict) -> dict:
        now_s = time.monotonic()

        # ── Sliding windows ──
        self.face_history.append(has_face)
        if len(self.face_history) > self.window_frames:
            self.face_history.pop(0)
        recent_face_ratio = sum(self.face_history) / max(len(self.face_history), 1)

        if features.get("headYaw") is not None:
            self.yaw_history.append(abs(features["headYaw"]))
            if len(self.yaw_history) > self.window_frames:
                self.yaw_history.pop(0)

        ear = features.get("eyeOpenRatio")
        if ear is not None:
            self.ear_history.append(ear)
            if len(self.ear_history) > self.window_frames:
                self.ear_history.pop(0)

        eyes_closed_count = sum(1 for e in self.ear_history[-15:] if e is not None and e < 0.12) if self.ear_history else 0
        features["eyesClosed"] = eyes_closed_count > 10

        # ── Away: bypass all smoothing, return immediately ──
        if not has_face or recent_face_ratio < 0.2:
            self.smoothed_score = 0.0
            features["activity"] = "away"
            sm_state = self.sm.update(0.0, recent_face_ratio, False, features.get("eyesClosed", False), now_s)
            return self._build_output(0.0, recent_face_ratio, features, sm_state, now_s)

        # ── Sub-scores ──
        subs = compute_sub_scores(features, recent_face_ratio, self.cal,
                                  self.yaw_history, eyes_closed_count)
        raw_score = weighted_score(subs, self.yaw_history, features)

        # ── Smoothing ──
        self.smoothed_score = 0.65 * self.smoothed_score + 0.35 * raw_score
        self.score_history.append(self.smoothed_score)
        if len(self.score_history) > self.window_frames:
            self.score_history.pop(0)

        # ── State machine ──
        sm_state = self.sm.update(self.smoothed_score, recent_face_ratio,
                                  True, features.get("eyesClosed", False), now_s)

        return self._build_output(self.smoothed_score, recent_face_ratio, features, sm_state, now_s,
                                  subs=subs)

    def _build_output(self, score: float, face_ratio: float, features: dict,
                      sm_state: dict, now_s: float, subs: dict | None = None) -> dict:
        presence = features.get("faceVisible", False) and face_ratio >= 0.2
        reason_codes = build_reason_codes(subs or {}, features, face_ratio)

        # Confidence: simple heuristic based on face ratio + frame reliability
        confidence = clamp01(face_ratio * 0.6 + (1.0 if features.get("frameReliable", False) else 0.0) * 0.4)

        return {
            "status":           sm_state["status"],
            "score":            round(float(score), 1),
            "confidence":       round(float(confidence), 3),
            "presence":         presence,
            "activity":         features.get("activity", "unknown"),
            "reasonCodes":      reason_codes,
            "subScores":        subs or {},
            "features":         features,
            "recentFaceRatio":  round(float(face_ratio), 2),
            "statusDurationMs": sm_state["statusDurationMs"],
            "pendingStatus":    sm_state["pendingStatus"],
            "pendingDurationMs": sm_state["pendingDurationMs"],
        }


# Final temporal analyzer: this later definition intentionally supersedes the
# early prototype above. It treats each frame as evidence, then makes status
# decisions from sliding-window statistics and an accumulated attention debt.
class StateMachine:
    """Slow state machine driven by temporal evidence, not single frames."""

    STATES = ["focused", "uncertain", "distracted", "away", "fatigue"]

    def __init__(self):
        self.current: str = "uncertain"
        self._pending: str | None = None
        self._pending_start_s: float = 0.0
        self._status_start_s: float = time.monotonic()

    def update(self, now_s: float, stats: dict, attention_debt: float,
               presence: bool, eyes_closed: bool) -> dict:
        away_s = float(stats.get("consecutiveAwaySeconds", 0.0))
        stable_face_s = float(stats.get("stableFaceSeconds", 0.0))
        enough_full_window = float(stats.get("fullWindowSeconds", 0.0)) >= 20.0

        if away_s >= 8.0:
            self._maybe_transition("away", 0.5, now_s)
            return self._result(now_s)

        if self.current == "away":
            self._maybe_transition("uncertain", 3.0, now_s, condition=presence and stable_face_s >= 3.0)
            return self._result(now_s)

        if eyes_closed and float(stats.get("eyesClosedSeconds", 0.0)) >= 3.0:
            self._maybe_transition("fatigue", 2.0, now_s)
            return self._result(now_s)

        if self.current == "fatigue":
            self._maybe_transition("uncertain", 5.0, now_s, condition=not eyes_closed and attention_debt < 45.0)
            return self._result(now_s)

        distraction_ready = (
            enough_full_window
            and attention_debt >= 35.0
            and (
                float(stats.get("fullLowScoreRatio", 0.0)) >= 0.55
                or float(stats.get("fullMedianScore", 100.0)) < 58.0
                or float(stats.get("fullSevereScoreRatio", 0.0)) >= 0.32
            )
        )
        uncertainty_ready = (
            attention_debt >= 24.0
            or float(stats.get("shortLowScoreRatio", 0.0)) >= 0.50
            or float(stats.get("shortMedianScore", 100.0)) < 60.0
        )
        recovery_ready = (
            attention_debt <= 22.0
            and float(stats.get("recoveryHighScoreRatio", 0.0)) >= 0.70
            and float(stats.get("recoveryMedianScore", 0.0)) >= 75.0
            and stable_face_s >= 10.0
        )

        if self.current == "focused":
            self._maybe_transition("uncertain", 5.0, now_s, condition=uncertainty_ready)
        elif self.current == "uncertain":
            if distraction_ready:
                self._maybe_transition("distracted", 12.0, now_s)
            elif recovery_ready:
                self._maybe_transition("focused", 12.0, now_s)
            else:
                self._cancel_pending()
        elif self.current == "distracted":
            self._maybe_transition("uncertain", 8.0, now_s, condition=attention_debt <= 30.0 and recovery_ready)
        else:
            self._maybe_transition("uncertain", 4.0, now_s)

        return self._result(now_s)

    def _maybe_transition(self, target: str, duration_s: float, now_s: float,
                          condition: bool = True) -> None:
        if not condition:
            self._cancel_pending()
            return
        if self.current == target:
            self._cancel_pending()
            return
        if self._pending == target:
            if now_s - self._pending_start_s >= duration_s:
                self.current = target
                self._status_start_s = now_s
                self._pending = None
        else:
            self._pending = target
            self._pending_start_s = now_s

    def _cancel_pending(self) -> None:
        self._pending = None

    def _result(self, now_s: float) -> dict:
        return {
            "status": self.current,
            "statusDurationMs": int((now_s - self._status_start_s) * 1000),
            "pendingStatus": self._pending,
            "pendingDurationMs": int((now_s - self._pending_start_s) * 1000) if self._pending else 0,
        }


class FocusAnalyzer:
    """Stateful analyzer with sliding-window evidence and attention debt."""

    def __init__(self, window_seconds: float = 30.0, fps_estimate: int = 15,
                 calibration_path: str | None = None):
        self.window_seconds = max(10.0, float(window_seconds))
        self.short_window_seconds = min(10.0, self.window_seconds)
        self.recovery_window_seconds = min(20.0, self.window_seconds)
        self.fps_estimate = max(int(fps_estimate), 1)
        self.window_frames = max(1, int(self.window_seconds * self.fps_estimate))
        self.cal = Calibration(calibration_path)
        self.face_history: list[bool] = []
        self.yaw_history: list[float] = []
        self.ear_history: list[float] = []
        self.nose_history: list[np.ndarray] = []
        self.score_samples: list[tuple[float, float]] = []
        self.score_history: list[float] = []
        self.smoothed_score: float = 50.0
        self.attention_debt: float = 0.0
        self._last_update_s: float | None = None
        self._face_seen_since_s: float | None = None
        self._face_missing_since_s: float | None = None
        self._eyes_closed_since_s: float | None = None
        self.sm = StateMachine()

    def update(self, has_face: bool, features: dict) -> dict:
        now_s = time.monotonic()
        dt = self._frame_dt(now_s)
        self._update_presence_runs(has_face, now_s)

        self.face_history.append(has_face)
        self.face_history = self.face_history[-self.window_frames:]
        recent_face_ratio = sum(self.face_history) / max(len(self.face_history), 1)

        if features.get("headYaw") is not None:
            self.yaw_history.append(abs(features["headYaw"]))
            self.yaw_history = self.yaw_history[-self.window_frames:]

        ear = features.get("eyeOpenRatio")
        if ear is not None:
            self.ear_history.append(ear)
            self.ear_history = self.ear_history[-self.window_frames:]

        eyes_closed_count = sum(1 for e in self.ear_history[-15:] if e is not None and e < 0.12) if self.ear_history else 0
        features["eyesClosed"] = eyes_closed_count > 10
        self._update_eye_run(features.get("eyesClosed", False), now_s)

        subs: dict = {}
        if has_face:
            subs = compute_sub_scores(features, recent_face_ratio, self.cal, self.yaw_history, eyes_closed_count)
            raw_score = weighted_score(subs, self.yaw_history, features)
        else:
            raw_score = 0.0
            features["activity"] = "away"

        self.smoothed_score = 0.85 * self.smoothed_score + 0.15 * raw_score
        self.score_history.append(self.smoothed_score)
        self.score_history = self.score_history[-self.window_frames:]
        self.score_samples.append((now_s, raw_score))
        self._trim_score_samples(now_s)

        self._update_attention_debt(raw_score, has_face, recent_face_ratio, features.get("eyesClosed", False), dt)
        stats = self._window_stats(now_s)
        presence = has_face and recent_face_ratio >= 0.2
        sm_state = self.sm.update(now_s, stats, self.attention_debt, presence, features.get("eyesClosed", False))

        return self._build_output(self.smoothed_score, recent_face_ratio, features, sm_state, subs, raw_score, stats)

    def _frame_dt(self, now_s: float) -> float:
        if self._last_update_s is None:
            self._last_update_s = now_s
            return 1.0 / self.fps_estimate
        dt = max(0.02, min(now_s - self._last_update_s, 1.0))
        self._last_update_s = now_s
        return dt

    def _update_presence_runs(self, has_face: bool, now_s: float) -> None:
        if has_face:
            if self._face_seen_since_s is None:
                self._face_seen_since_s = now_s
            self._face_missing_since_s = None
        else:
            if self._face_missing_since_s is None:
                self._face_missing_since_s = now_s
            self._face_seen_since_s = None

    def _update_eye_run(self, eyes_closed: bool, now_s: float) -> None:
        if eyes_closed:
            if self._eyes_closed_since_s is None:
                self._eyes_closed_since_s = now_s
        else:
            self._eyes_closed_since_s = None

    def _trim_score_samples(self, now_s: float) -> None:
        cutoff = now_s - self.window_seconds
        self.score_samples = [(ts, score) for ts, score in self.score_samples if ts >= cutoff]

    def _update_attention_debt(self, raw_score: float, has_face: bool,
                               recent_face_ratio: float, eyes_closed: bool, dt: float) -> None:
        if not has_face:
            delta = 1.8 * dt
        elif raw_score >= 75:
            delta = -1.2 * dt
        elif raw_score >= 60:
            delta = 0.15 * dt
        elif raw_score >= 45:
            delta = 0.45 * dt
        else:
            delta = 1.0 * dt
        if recent_face_ratio < 0.7:
            delta += 0.4 * dt
        if eyes_closed:
            delta += 1.2 * dt
        self.attention_debt = max(0.0, min(100.0, self.attention_debt + delta))

    def _window_stats(self, now_s: float) -> dict:
        full = self._score_stats(now_s, self.window_seconds)
        short = self._score_stats(now_s, self.short_window_seconds)
        recovery = self._score_stats(now_s, self.recovery_window_seconds)
        return {
            "fullWindowSeconds": full["seconds"],
            "fullMeanScore": full["mean"],
            "fullMedianScore": full["median"],
            "fullLowScoreRatio": full["lowRatio"],
            "fullSevereScoreRatio": full["severeRatio"],
            "shortMedianScore": short["median"],
            "shortLowScoreRatio": short["lowRatio"],
            "recoveryMedianScore": recovery["median"],
            "recoveryHighScoreRatio": recovery["highRatio"],
            "trendSlope": full["trendSlope"],
            "consecutiveAwaySeconds": 0.0 if self._face_missing_since_s is None else round(now_s - self._face_missing_since_s, 2),
            "stableFaceSeconds": 0.0 if self._face_seen_since_s is None else round(now_s - self._face_seen_since_s, 2),
            "eyesClosedSeconds": 0.0 if self._eyes_closed_since_s is None else round(now_s - self._eyes_closed_since_s, 2),
        }

    def _score_stats(self, now_s: float, seconds: float) -> dict:
        samples = [(ts, score) for ts, score in self.score_samples if now_s - ts <= seconds]
        values = [score for _, score in samples]
        if not values:
            return {"seconds": 0.0, "mean": 0.0, "median": 0.0, "lowRatio": 0.0,
                    "severeRatio": 0.0, "highRatio": 0.0, "trendSlope": 0.0}
        ordered = sorted(values)
        mid = len(ordered) // 2
        median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
        mean = sum(values) / len(values)
        chunk = max(1, len(values) // 3)
        trend_slope = ((sum(values[-chunk:]) / chunk) - (sum(values[:chunk]) / chunk)) / max(seconds, 1.0)
        span = samples[-1][0] - samples[0][0] if len(samples) > 1 else 0.0
        return {
            "seconds": round(float(min(seconds, max(span, 0.0))), 2),
            "mean": round(float(mean), 1),
            "median": round(float(median), 1),
            "lowRatio": round(sum(1 for score in values if score < 60) / len(values), 3),
            "severeRatio": round(sum(1 for score in values if score < 45) / len(values), 3),
            "highRatio": round(sum(1 for score in values if score >= 75) / len(values), 3),
            "trendSlope": round(float(trend_slope), 3),
        }

    def _build_output(self, score: float, face_ratio: float, features: dict,
                      sm_state: dict, subs: dict | None, raw_score: float,
                      stats: dict) -> dict:
        presence = features.get("faceVisible", False) and face_ratio >= 0.2
        reason_codes = build_reason_codes(subs or {}, features, face_ratio)
        if self.attention_debt >= 35:
            reason_codes.append("attention_debt_high")
        elif self.attention_debt >= 24:
            reason_codes.append("attention_debt_rising")
        confidence = clamp01(face_ratio * 0.6 + (1.0 if features.get("frameReliable", False) else 0.0) * 0.4)
        return {
            "status":           sm_state["status"],
            "score":            round(float(score), 1),
            "instantScore":     round(float(raw_score), 1),
            "attentionDebt":    round(float(self.attention_debt), 1),
            "confidence":       round(float(confidence), 3),
            "presence":         presence,
            "activity":         features.get("activity", "unknown"),
            "reasonCodes":      reason_codes,
            "subScores":        subs or {},
            "features":         features,
            "windowStats":      stats,
            "recentFaceRatio":  round(float(face_ratio), 2),
            "statusDurationMs": sm_state["statusDurationMs"],
            "pendingStatus":    sm_state["pendingStatus"],
            "pendingDurationMs": sm_state["pendingDurationMs"],
        }


def compute_sub_scores(features: dict, recent_face_ratio: float,
                       cal: Calibration, yaw_history: list[float],
                       eyes_closed_count: int) -> dict:
    """Compute scores against the calibrated posture for the current camera."""
    yaw = features.get("headYaw")
    pitch = features.get("headPitch")
    roll = features.get("headRoll")
    ear = features.get("eyeOpenRatio") or 0.0
    eye_reliable = features.get("eyeReliable", False)
    stability = features.get("motionStability", 0.5)
    center_x = features.get("faceCenterX")
    center_y = features.get("faceCenterY")
    area = features.get("faceBoxArea") or 0.0

    presence_score = clamp01(recent_face_ratio)

    yaw_delta = abs(float(yaw) - cal.screen_yaw) if yaw is not None else 90.0
    pitch_delta = abs(float(pitch) - cal.screen_pitch) if pitch is not None else 90.0
    roll_delta = abs(float(roll) - cal.screen_roll) if roll is not None else 45.0
    yaw_score = safe_quadratic_score(yaw_delta, cal.yaw_safe_delta, cal.yaw_hard_delta)
    pitch_score = safe_quadratic_score(pitch_delta, cal.pitch_safe_delta, cal.pitch_hard_delta)
    roll_score = safe_quadratic_score(roll_delta, cal.roll_safe_delta, cal.roll_hard_delta)
    head_ori = yaw_score * 0.45 + pitch_score * 0.40 + roll_score * 0.15

    if eye_reliable and ear > 0.0:
        baseline = cal.screen_eye_open if cal.has_calibration else 0.25
        eye_state = clamp01(min(ear / max(baseline * 0.7, 0.01), 1.0))
        if eyes_closed_count > 10:
            eye_state *= 0.5
    else:
        eye_state = 0.5

    if center_x is not None and center_y is not None:
        center_delta = math.sqrt((float(center_x) - cal.face_center_x) ** 2 + (float(center_y) - cal.face_center_y) ** 2)
        center_score = safe_quadratic_score(center_delta, cal.center_safe_delta, cal.center_hard_delta)
    else:
        center_score = 0.0

    if cal.face_box_area > 0 and area > 0:
        area_ratio = float(area) / max(cal.face_box_area, 1e-6)
        distance_score = band_quadratic_score(
            area_ratio,
            cal.area_min_ratio,
            cal.area_max_ratio,
            cal.area_hard_min_ratio,
            cal.area_hard_max_ratio,
        )
    else:
        distance_score = 0.5

    posture_match = head_ori * 0.50 + center_score * 0.30 + distance_score * 0.20
    return {
        "presence":         round(float(presence_score), 4),
        "headOrientation":  round(float(head_ori), 4),
        "eyeState":         round(float(eye_state), 4),
        "motionStability":  round(float(stability), 4),
        "taskPosture":      round(float(posture_match), 4),
        "facePosition":     round(float(center_score), 4),
        "faceDistance":     round(float(distance_score), 4),
    }


def weighted_score(subs: dict, yaw_history: list[float], features: dict) -> float:
    """Weighted combination of calibrated sub-scores to 0-100."""
    w_eye = 0.10 if features.get("eyeReliable", False) else 0.05
    raw = (
        0.25 * subs["presence"] +
        0.20 * subs["headOrientation"] +
        w_eye * subs["eyeState"] +
        0.15 * subs["motionStability"] +
        (0.40 - w_eye) * subs["taskPosture"]
    )
    return clamp01(raw) * 100.0
