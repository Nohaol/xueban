"""FastAPI server exposing focus detection via HTTP/WebSocket.

Start:  python -m uvicorn focus_lab.serve_api:app --host 0.0.0.0 --port 8010

Endpoints:
  GET  /health
  GET  /state
  GET  /snapshot.jpg
  GET  /video_feed
  WS   /ws
"""
from __future__ import annotations
import asyncio
import time
import threading
import os
import sys

import cv2
import mediapipe
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.responses import Response

sys.path.insert(0, os.path.dirname(__file__))
from focus_features import (
    landmark_to_ndarray, compute_features, no_face_features, FocusAnalyzer,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")

app = FastAPI(title="Focus Monitor API")

# ── Global state ──────────────────────────────────────────────
_state_lock = threading.Lock()
_latest_frame: np.ndarray | None = None
_latest_jpeg: bytes | None = None
_latest_state: dict = {"ok": True, "mode": "boot", "status": "away", "score": 0,
                       "presence": False, "reason": "starting", "features": {},
                       "updatedAt": 0}
_analyzer = FocusAnalyzer(window_seconds=2.0, fps_estimate=15)
_running = True


def capture_loop(camera_index: int = 0):
    """Background thread: read camera, run MediaPipe, update global state."""
    global _latest_frame, _latest_jpeg, _latest_state, _running

    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
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

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_ms = int(time.time() * 1000)

    while _running:
        ok, frame_bgr = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        h, w = frame_bgr.shape[:2]
        ts_ms = int(time.time() * 1000)
        if ts_ms <= prev_ms:
            ts_ms = prev_ms + 1
        prev_ms = ts_ms

        # MediaPipe
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(mp_image, ts_ms)

        has_face = len(result.face_landmarks) > 0
        features: dict

        transform = result.facial_transformation_matrixes[0] if (
            result.facial_transformation_matrixes and len(result.facial_transformation_matrixes) > 0
        ) else None

        if has_face:
            landmarks = result.face_landmarks[0]
            lm_3d = landmark_to_ndarray(landmarks)
            features = compute_features(lm_3d, (h, w),
                                        transform_matrix=transform,
                                        nose_history=_analyzer.nose_history)
            nose_xy = np.array([float(landmarks[1].x), float(landmarks[1].y)])
            _analyzer.nose_history.append(nose_xy)
            if len(_analyzer.nose_history) > _analyzer.window_frames:
                _analyzer.nose_history.pop(0)
            for lm in landmarks:
                px, py = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame_bgr, (px, py), 1, (100, 200, 120), -1)
        else:
            features = no_face_features()

        state = _analyzer.update(has_face, features)

        cv2.putText(frame_bgr, f"{state['status']} {state['score']:.0f}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        jpeg_bytes = buf.tobytes() if ok else None

        with _state_lock:
            _latest_frame = frame_bgr
            _latest_jpeg = jpeg_bytes
            _latest_state = {
                "ok": True,
                "mode": "camera",
                "status": state["status"],
                "score": state["score"],
                "confidence": state.get("confidence", 0),
                "presence": state["presence"],
                "activity": state.get("activity", "unknown"),
                "reasonCodes": state.get("reasonCodes", []),
                "subScores": state.get("subScores", {}),
                "features": features,
                "statusDurationMs": state.get("statusDurationMs", 0),
                "pendingStatus": state.get("pendingStatus"),
                "updatedAt": ts_ms,
            }

    cap.release()
    landmarker.close()


@app.on_event("startup")
async def startup():
    thread = threading.Thread(target=capture_loop, args=(0,), daemon=True)
    thread.start()


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/state")
async def get_state():
    with _state_lock:
        return _latest_state


@app.get("/snapshot.jpg")
async def snapshot():
    with _state_lock:
        jpeg = _latest_jpeg
    if jpeg is None:
        return Response(content=b"", media_type="image/jpeg", status_code=204)
    return Response(content=jpeg, media_type="image/jpeg")


@app.get("/video_feed")
async def video_feed():
    """MJPEG stream of the latest annotated frames."""
    async def generate():
        while True:
            with _state_lock:
                jpeg = _latest_jpeg
            if jpeg is not None:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            await asyncio.sleep(0.1)
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    import json
    while True:
        try:
            with _state_lock:
                state = _latest_state.copy()
            await ws.send_text(json.dumps(state, ensure_ascii=False))
            await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            break
        except Exception:
            break


@app.on_event("shutdown")
async def shutdown():
    global _running
    _running = False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
