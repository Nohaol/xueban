"""Replay a recorded video through the focus analyzer and output CSV metrics."""
import cv2
import mediapipe
import numpy as np
import time
import os
import sys
import csv
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.path.dirname(__file__))
from focus_features import (
    landmark_to_ndarray,
    compute_features,
    no_face_features,
    FocusAnalyzer,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")


def replay(video_path: str, output_csv: str | None = None,
           show: bool = True, fps_limit: int = 0):
    """Replay a video through the focus analyzer.

    Args:
        video_path: path to input video file
        output_csv: optional path to write CSV metrics
        show: display the output window
        fps_limit: 0 = real-time, >0 = max fps for fast replay
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: cannot open {video_path}")
        return

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

    analyzer = FocusAnalyzer(window_seconds=2.0, fps_estimate=15)

    csv_file = None
    csv_writer = None
    if output_csv:
        csv_file = open(output_csv, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "timestamp_ms", "status", "score", "presence", "confidence",
            "activity", "reasonCodes",
            "sub_presence", "sub_headOrientation", "sub_eyeState",
            "sub_motionStability", "sub_taskPosture",
            "headYaw", "headPitch", "eyeOpenRatio",
            "leftEyeOpenRatio", "rightEyeOpenRatio",
            "faceBoxArea", "faceCenterX", "faceCenterY",
            "motionStability", "eyeReliable", "frameReliable",
            "pendingStatus", "statusDurationMs",
        ])

    frame_count = 0
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    frame_interval = 1.0 / video_fps  # seconds per frame
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Video: {os.path.basename(video_path)}, {video_fps:.1f} fps, ~{total_frames} frames")
    if output_csv:
        print(f"CSV output: {output_csv}")
    print("Press 'q' to quit.\n")

    prev_ms = int(time.time() * 1000)
    start_wall = time.perf_counter()

    while True:
        t0 = time.perf_counter()
        ok, frame = cap.read()
        if not ok:
            break

        h, w = frame.shape[:2]
        frame_count += 1

        # Simulated real-time timestamp for MediaPipe (monotonic ms)
        sim_ms = int(frame_count * frame_interval * 1000)
        if sim_ms <= prev_ms:
            sim_ms = prev_ms + 1
        prev_ms = sim_ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(mp_image, sim_ms)

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
            nose_xy = np.array([float(landmarks[1].x), float(landmarks[1].y)])
            analyzer.nose_history.append(nose_xy)
            if len(analyzer.nose_history) > analyzer.window_frames:
                analyzer.nose_history.pop(0)
        else:
            features = no_face_features()

        state = analyzer.update(has_face, features)

        # CSV output
        if csv_writer:
            feat = features
            subs = state.get("subScores", {})
            csv_writer.writerow([
                sim_ms, state["status"], state["score"], state["presence"],
                state.get("confidence", 0),
                state.get("activity", ""),
                "|".join(state.get("reasonCodes", [])),
                subs.get("presence", 0), subs.get("headOrientation", 0),
                subs.get("eyeState", 0), subs.get("motionStability", 0),
                subs.get("taskPosture", 0),
                feat.get("headYaw"), feat.get("headPitch"),
                feat.get("eyeOpenRatio"),
                feat.get("leftEyeOpenRatio"), feat.get("rightEyeOpenRatio"),
                feat.get("faceBoxArea"), feat.get("faceCenterX"), feat.get("faceCenterY"),
                feat.get("motionStability"), feat.get("eyeReliable"), feat.get("frameReliable"),
                state.get("pendingStatus", ""), state.get("statusDurationMs", 0),
            ])
            if frame_count % 50 == 0:
                csv_file.flush()

        # Progress
        elapsed = time.perf_counter() - start_wall
        print(f"  frame {frame_count}/{total_frames} | "
              f"status={state['status']:<10} score={state['score']:5.1f} | "
              f"elapsed={elapsed:.1f}s", end="\r", flush=True)

        # Display
        if show:
            info_bar = np.zeros((40, w, 3), dtype=np.uint8)
            info_bar[:] = (50, 50, 50)
            cv2.putText(info_bar, f"Frame {frame_count} | Status: {state['status']} | Score: {state['score']:.1f}",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
            display = np.vstack([info_bar, frame])
            cv2.imshow("Replay", display)

        # Rate control
        if fps_limit > 0:
            wait_ms = 1
        else:
            wait_ms = max(1, int(frame_interval * 1000))
        if cv2.waitKey(wait_ms) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    if csv_file:
        csv_file.close()
    elapsed = time.perf_counter() - start_wall
    print(f"\nDone. {frame_count} frames in {elapsed:.1f}s "
          f"({frame_count / elapsed:.1f} fps).")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Path to video file")
    ap.add_argument("--csv", default=None, help="Output CSV path")
    ap.add_argument("--no-show", action="store_true", help="Hide window")
    ap.add_argument("--fast", type=int, default=0, help="FPS limit (0=realtime)")
    args = ap.parse_args()
    replay(args.video, args.csv, show=not args.no_show, fps_limit=args.fast)
