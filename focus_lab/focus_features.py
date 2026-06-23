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
    def has_calibration(self) -> bool:
        return bool(self.data)

    @property
    def screen_yaw(self) -> float:
        return float(self.data.get("screen", {}).get("yawMedian", 0.0))

    @property
    def screen_pitch(self) -> float:
        return float(self.data.get("screen", {}).get("pitchMedian", 0.0))

    @property
    def screen_eye_open(self) -> float:
        return float(self.data.get("screen", {}).get("eyeOpenMedian", 0.25))

    @property
    def writing_pitch(self) -> float:
        return float(self.data.get("writing", {}).get("pitchMedian", -18.0))

    @property
    def yaw_soft_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("yawSoftDelta", 15.0))

    @property
    def yaw_hard_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("yawHardDelta", 25.0))

    @property
    def pitch_writing_delta(self) -> float:
        return float(self.data.get("thresholds", {}).get("pitchWritingDelta", 25.0))

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
        "headYaw":        None, "headPitch": None, "headPoseSource": None,
        "leftEyeOpenRatio": None, "rightEyeOpenRatio": None,
        "eyeOpenRatio":   None, "eyeReliable": False, "eyesClosed": False,
        "faceBoxArea":    0.0,  "faceCenterX": None, "faceCenterY": None,
        "landmarkQuality": 0.0, "frameReliable": False,
        "motionStability": 0.0, "activity": "away",
    }


# ── Sub-scores (0-1 scale) ──────────────────────────────────────
def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


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
        self.current: str = "away"
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
