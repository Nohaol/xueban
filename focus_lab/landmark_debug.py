"""Minimal FaceMesh debug: show landmarks on live camera feed."""
import cv2
import mediapipe
import numpy as np
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")

# Face oval indices (MediaPipe 478-landmark topology)
# Circumference of the face: jawline + forehead
FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]
# Left eye contour
LEFT_EYE_CONTOUR = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
# Right eye contour
RIGHT_EYE_CONTOUR = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
# Lips outer
LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]

def main():
    # Create FaceLandmarker in VIDEO mode
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

    print("Press 'q' to quit. Face the camera...")
    prev_ms = int(time.time() * 1000)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed")
            break

        h, w = frame.shape[:2]
        ts_ms = int(time.time() * 1000)
        if ts_ms <= prev_ms:
            ts_ms = prev_ms + 1
        prev_ms = ts_ms

        # BGR -> RGB -> mp.Image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)

        result = landmarker.detect_for_video(mp_image, ts_ms)

        face_count = len(result.face_landmarks)
        print(f"ts={ts_ms} faces={face_count}", end="\r", flush=True)

        if face_count > 0:
            landmarks = result.face_landmarks[0]
            # Draw landmarks
            for lm in landmarks:
                x, y = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (x, y), 1, (0, 255, 127), -1)

            # Draw face contours
            for contour in [FACE_OVAL, LEFT_EYE_CONTOUR, RIGHT_EYE_CONTOUR, LIPS_OUTER]:
                for i in range(len(contour)):
                    a, b = contour[i], contour[(i + 1) % len(contour)]
                    if a < len(landmarks) and b < len(landmarks):
                        x1, y1 = int(landmarks[a].x * w), int(landmarks[a].y * h)
                        x2, y2 = int(landmarks[b].x * w), int(landmarks[b].y * h)
                        cv2.line(frame, (x1, y1), (x2, y2), (200, 220, 200), 1)

            cv2.putText(frame, f"Landmarks: {len(landmarks)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 100), 2)
        else:
            cv2.putText(frame, "No face detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("FaceMesh Debug", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()

if __name__ == "__main__":
    main()
