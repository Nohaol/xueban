"""10-second calibration wizard for personal baseline.

Captures 3 states:
  1. screen  — face the screen (5s)
  2. writing — look down at desk (5s)
  3. away    — leave the frame (3s)

Outputs: focus_lab/config/calibration.json
"""
import cv2
import mediapipe
import numpy as np
import time
import os
import sys
import json
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.path.dirname(__file__))
from focus_features import (
    landmark_to_ndarray, eye_aspect_ratio, LEFT_EYE, RIGHT_EYE,
    estimate_head_pose_from_matrix, estimate_head_pose_pnp,
    FocusAnalyzer, reload_calibration,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
OUTPUT_PATH = os.path.join(CONFIG_DIR, "calibration.json")


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.median(values))


def calibrate():
    print("=" * 50)
    print("  Focus Lab Calibration")
    print("=" * 50)
    print()

    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Collectors
    profiles: dict[str, dict[str, list[float]]] = {
        "screen":  {"yaw": [], "pitch": [], "eyeOpen": [], "faceBoxArea": []},
        "writing": {"yaw": [], "pitch": [], "eyeOpen": [], "faceBoxArea": []},
    }

    for phase, seconds, instruction in [
        ("screen",  5, "Face the screen naturally. Look straight ahead."),
        ("writing", 5, "Look down at your desk as if writing on paper."),
        ("away",    3, "Step away from the camera (leave the frame)."),
    ]:
        print(f"\n>>> Phase: {phase.upper()} ({seconds}s)")
        print(f"    {instruction}")
        print("    Starting in 2 seconds...")
        time.sleep(2)

        start = time.perf_counter()
        prev_ms = int(time.time() * 1000)
        frame_count = 0

        while time.perf_counter() - start < seconds:
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            ts_ms = int(time.time() * 1000)
            if ts_ms <= prev_ms:
                ts_ms = prev_ms + 1
            prev_ms = ts_ms

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(mp_image, ts_ms)

            has_face = len(result.face_landmarks) > 0
            elapsed = time.perf_counter() - start
            remain = seconds - elapsed

            if phase == "away":
                cv2.putText(frame, f"AWAY phase: step out ({remain:.1f}s)", (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (70, 70, 230), 2)
                cv2.imshow("Calibration", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            if not has_face:
                cv2.putText(frame, f"No face detected ({remain:.1f}s)", (30, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("Calibration", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            landmarks = result.face_landmarks[0]
            lm_3d = landmark_to_ndarray(landmarks)
            transform = result.facial_transformation_matrixes[0] if (
                result.facial_transformation_matrixes and len(result.facial_transformation_matrixes) > 0
            ) else None

            # Head pose
            pose = estimate_head_pose_from_matrix(transform)
            if pose is None:
                pose = estimate_head_pose_pnp(lm_3d, (h, w))
            if pose:
                profiles[phase]["yaw"].append(pose.get("yaw", 0) or 0)
                profiles[phase]["pitch"].append(pose.get("pitch", 0) or 0)

            # Eyes
            left_ear = eye_aspect_ratio(lm_3d, LEFT_EYE)
            right_ear = eye_aspect_ratio(lm_3d, RIGHT_EYE)
            profiles[phase]["eyeOpen"].append((left_ear + right_ear) / 2)

            # Face box area
            xs = lm_3d[:, 0]
            ys = lm_3d[:, 1]
            box_area = (float(xs.max()) - float(xs.min())) * (float(ys.max()) - float(ys.min()))
            profiles[phase]["faceBoxArea"].append(box_area)

            frame_count += 1
            cv2.putText(frame, f"{phase.upper()} [{frame_count}] ({remain:.1f}s)", (30, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (70, 200, 130), 2)
            cv2.imshow("Calibration", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()

    # Build calibration
    result = {
        "screen": {
            "yawMedian":    round(_median(profiles["screen"]["yaw"]), 1),
            "pitchMedian":  round(_median(profiles["screen"]["pitch"]), 1),
            "eyeOpenMedian": round(_median(profiles["screen"]["eyeOpen"]), 4),
            "faceBoxAreaMedian": round(_median(profiles["screen"]["faceBoxArea"]), 4),
        },
        "writing": {
            "yawMedian":    round(_median(profiles["writing"]["yaw"]), 1),
            "pitchMedian":  round(_median(profiles["writing"]["pitch"]), 1),
            "eyeOpenMedian": round(_median(profiles["writing"]["eyeOpen"]), 4),
            "faceBoxAreaMedian": round(_median(profiles["writing"]["faceBoxArea"]), 4),
        },
        "thresholds": {
            "yawSafeDelta": 12,
            "yawSoftDelta": 15,
            "yawHardDelta": 25,
            "pitchSafeDelta": 12,
            "pitchWritingDelta": 25,
            "pitchHardDelta": 30,
            "rollSafeDelta": 8,
            "rollHardDelta": 22,
            "centerSafeDelta": 0.08,
            "centerHardDelta": 0.24,
            "areaMinRatio": 0.55,
            "areaMaxRatio": 1.8,
            "areaHardMinRatio": 0.35,
            "areaHardMaxRatio": 2.6,
            "eyeClosedRatio": 0.55,
        },
    }

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print("Calibration saved!")
    print(f"  {OUTPUT_PATH}")
    print()
    print(f"  Screen:  yaw={result['screen']['yawMedian']:.1f}  pitch={result['screen']['pitchMedian']:.1f}  eye={result['screen']['eyeOpenMedian']:.3f}")
    print(f"  Writing: yaw={result['writing']['yawMedian']:.1f}  pitch={result['writing']['pitchMedian']:.1f}  eye={result['writing']['eyeOpenMedian']:.3f}")
    print()
    print("Now run: python focus_lab\\run_realtime.py")
    print("=" * 50)

    # Reload calibration so run_realtime picks it up
    reload_calibration(OUTPUT_PATH)


if __name__ == "__main__":
    calibrate()
