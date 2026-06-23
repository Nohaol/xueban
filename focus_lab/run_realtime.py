"""Real-time focus detection v2 — sub-scores + state machine + debug overlay."""
import cv2
import mediapipe
import numpy as np
import time
import os
import sys
from datetime import datetime
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.path.dirname(__file__))
from focus_features import (
    landmark_to_ndarray,
    compute_features,
    no_face_features,
    FocusAnalyzer,
    get_calibration,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")

FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]
LEFT_EYE_CONTOUR = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE_CONTOUR = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]

STATUS_COLORS = {
    "focused":    (70, 180, 70),
    "uncertain":  (70, 180, 220),
    "distracted": (70, 100, 230),
    "away":       (70, 70, 230),
    "fatigue":    (120, 60, 220),
}


def draw_landmarks(frame, landmarks, w, h):
    for lm in landmarks:
        x, y = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (x, y), 1, (100, 200, 120), -1)
    for contour in [FACE_OVAL, LEFT_EYE_CONTOUR, RIGHT_EYE_CONTOUR, LIPS_OUTER]:
        for i in range(len(contour)):
            a, b = contour[i], contour[(i + 1) % len(contour)]
            if a < len(landmarks) and b < len(landmarks):
                x1, y1 = int(landmarks[a].x * w), int(landmarks[a].y * h)
                x2, y2 = int(landmarks[b].x * w), int(landmarks[b].y * h)
                cv2.line(frame, (x1, y1), (x2, y2), (180, 210, 180), 1)


def draw_overlay(frame, state: dict, fps: float):
    h, w = frame.shape[:2]
    ow = 420  # wider for new fields
    overlay = np.zeros((h, ow, 3), dtype=np.uint8)
    overlay[:] = (35, 35, 35)

    y = 28
    gap = 22

    # Status
    status = state["status"]
    color = STATUS_COLORS.get(status, (200, 200, 200))
    cv2.putText(overlay, f"Status: {status.upper()}", (12, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    y += 30
    # Pending
    pending = state.get("pendingStatus")
    if pending:
        dur = state.get("pendingDurationMs", 0)
        cv2.putText(overlay, f"  -> {pending} ({dur}ms)", (12, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
        y += 18

    # Score + confidence
    cv2.putText(overlay, f"Score: {state['score']:.1f}  conf={state.get('confidence', 0):.2f}",
                (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1)
    y += gap

    cv2.putText(overlay, f"Activity: {state.get('activity', '?')} | FaceRatio: {state.get('recentFaceRatio', 0):.2f}",
                (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    y += gap + 4

    # Sub-scores
    subs = state.get("subScores", {})
    if subs:
        cv2.putText(overlay, "-- Sub-scores --", (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 160), 1)
        y += 18
        for key, label in [("presence", "Pres"), ("headOrientation", "Head"),
                           ("eyeState", "Eye"), ("motionStability", "Motn"),
                           ("taskPosture", "Task")]:
            val = subs.get(key, 0)
            cv2.putText(overlay, f"  {label}: {val:.2f}", (12, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (210, 210, 210), 1)
            # mini bar
            bar_x, bar_w = 90, 60
            cv2.rectangle(overlay, (bar_x, y - 8), (bar_x + bar_w, y - 2), (80, 80, 80), -1)
            cv2.rectangle(overlay, (bar_x, y - 8), (bar_x + int(bar_w * val), y - 2),
                          (100, 200, 120), -1)
            y += 16

    y += 4

    # Features
    feat = state["features"]
    cv2.putText(overlay, "-- Features --", (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 160), 1)
    y += 18
    for key, label in [("headYaw", "Yaw"), ("headPitch", "Pitch"),
                       ("eyeOpenRatio", "EyeOpen"),
                       ("leftEyeOpenRatio", " L-Eye"), ("rightEyeOpenRatio", " R-Eye"),
                       ("motionStability", "Motion"), ("faceBoxArea", "BoxArea")]:
        val = feat.get(key)
        if val is not None:
            cv2.putText(overlay, f"  {label}: {val:.2f}", (12, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1)
            y += 16

    y += 4
    # Reason codes
    reasons = state.get("reasonCodes", [])
    label = ", ".join(reasons[:6]) if reasons else "none"
    cv2.putText(overlay, f"Reasons: {label}", (12, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)
    y += 24
    cv2.putText(overlay, f"FPS: {fps:.0f}", (12, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

    combined = np.hstack([frame, overlay])
    return combined


def main():
    print(f"Model: {MODEL_PATH}  exists={os.path.isfile(MODEL_PATH)}")
    cal = get_calibration()
    if cal.has_calibration:
        print(f"Calibration loaded: screen_yaw={cal.screen_yaw:.1f} screen_pitch={cal.screen_pitch:.1f}")

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

    analyzer = FocusAnalyzer(window_seconds=2.0, fps_estimate=15)
    recording = False
    video_writer = None

    print("Keys: q=quit  s=save frame  r=toggle record  c=cycle status  p=print state")
    prev_ms = int(time.time() * 1000)
    fps_counter = []

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed, retrying...")
            time.sleep(0.1)
            continue

        t0 = time.perf_counter()
        h, w = frame.shape[:2]
        ts_ms = int(time.time() * 1000)
        if ts_ms <= prev_ms:
            ts_ms = prev_ms + 1
        prev_ms = ts_ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(mp_image, ts_ms)

        has_face = len(result.face_landmarks) > 0
        transform = result.facial_transformation_matrixes[0] if (
            result.facial_transformation_matrixes and len(result.facial_transformation_matrixes) > 0
        ) else None

        if has_face:
            landmarks = result.face_landmarks[0]
            lm_3d = landmark_to_ndarray(landmarks)
            features = compute_features(lm_3d, (h, w),
                                        transform_matrix=transform,
                                        nose_history=analyzer.nose_history)
            draw_landmarks(frame, landmarks, w, h)
            # Update nose history
            nose_xy = np.array([float(landmarks[1].x), float(landmarks[1].y)])
            analyzer.nose_history.append(nose_xy)
            if len(analyzer.nose_history) > analyzer.window_frames:
                analyzer.nose_history.pop(0)
        else:
            features = no_face_features()

        state = analyzer.update(has_face, features)

        # FPS
        fps_counter.append(time.perf_counter() - t0)
        if len(fps_counter) > 30:
            fps_counter.pop(0)
        fps = 1.0 / (sum(fps_counter) / len(fps_counter)) if fps_counter else 0

        output = draw_overlay(frame, state, fps)

        color = STATUS_COLORS.get(state["status"], (200, 200, 200))
        cv2.rectangle(output, (0, 0), (640, 5), color, -1)

        cv2.imshow("Focus Monitor v2", output)

        if recording and video_writer is not None:
            video_writer.write(output)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(os.path.dirname(__file__), "outputs", f"frame_{ts}.jpg")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            cv2.imwrite(out_path, output)
            print(f"Saved: {out_path}")
        elif key == ord('r'):
            recording = not recording
            if recording:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = os.path.join(os.path.dirname(__file__), "outputs", f"recording_{ts}.avi")
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                video_writer = cv2.VideoWriter(out_path, fourcc, 10.0, (output.shape[1], output.shape[0]))
                print(f"Recording: {out_path}")
            else:
                if video_writer:
                    video_writer.release()
                    video_writer = None
                print("Recording stopped.")
        elif key == ord('p'):
            import json
            simple = {k: v for k, v in state.items()
                      if k not in ("features", "subScores")}
            simple["subScores"] = state.get("subScores", {})
            simple["reasonCodes"] = state.get("reasonCodes", [])
            print(json.dumps(simple, ensure_ascii=False, indent=2))

    cap.release()
    if video_writer:
        video_writer.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print("Done.")


if __name__ == "__main__":
    main()
