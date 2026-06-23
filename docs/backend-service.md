# Backend Edge Node

## What is included

The repository now includes a local Python backend under `backend/`:

- `backend/main.py`
  FastAPI app with `/ws`, `/video_feed`, `/snapshot.jpg`, `/control`, `/state`, and `/health`.
- `backend/engine.py`
  Local runtime loop for source selection, camera capture, MediaPipe Face Landmarker analysis, score calculation, overlay rendering, and mock fallback.
- `backend/schemas.py`
  Shared request and response models.

## Runtime behavior

The backend can run in two modes:

- `camera`
  Uses MediaPipe Face Landmarker-based live analysis when a readable camera or network stream is available. OpenCV still handles camera/network capture and remains as a fallback analyzer.
- `mock`
  Automatically activates if dependencies are missing, the source cannot be opened, or `FOCUS_FORCE_MOCK=1` is set.

That fallback matters because it lets you demo the entire loop before the camera pipeline is stable.

## Supported source types

The backend now supports two source classes:

- `local_camera`
  The webcam attached to this PC.
- `network_camera`
  A network stream or snapshot endpoint, such as RTSP, MJPEG, or HTTP snapshot.

The phone does not process video directly. It only selects a source. This PC still pulls the source and runs the analysis.

## Source management APIs

- `GET /sources`
  Returns all known sources and the current selection.
- `POST /sources/select`
  Switches the active source.
- `POST /sources/network`
  Registers a network camera source.

Example network camera payload:

```json
{
  "label": "Desk RTSP Cam",
  "url": "rtsp://192.168.137.50:554/stream1",
  "transport": "stream"
}
```

Example snapshot camera payload:

```json
{
  "label": "Hallway Snapshot Cam",
  "url": "http://192.168.137.60/snapshot.jpg",
  "transport": "snapshot"
}
```

## Recommended local run

Use a Python environment that can install `mediapipe`. If your current interpreter cannot install it, switch to Python 3.11 for the backend.

Install dependencies:

```powershell
py -3.11 -m pip install -r backend\requirements.txt
```

Run the server:

```powershell
py -3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Force mock mode if you only want a closed-loop UI demo:

```powershell
$env:FOCUS_FORCE_MOCK='1'
py -3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Environment variables

- `FOCUS_FORCE_MOCK`
- `FOCUS_CAMERA_SOURCE`
- `FOCUS_STUDENT_LABEL`
- `FOCUS_FRAME_WIDTH`
- `FOCUS_FRAME_HEIGHT`
- `FOCUS_ANALYSIS_FPS`
- `FOCUS_AWAY_TIMEOUT_SECONDS`
- `FOCUS_JPEG_QUALITY`

## Notes on the scoring logic

The current scoring logic is heuristic, not a trained model:

- `gaze`
  Estimated from face position and eye detection inside the frame.
- `posture`
  Estimated from face position, size, and offset relative to the expected study zone.
- `stability`
  Estimated from short-window grayscale motion.
- `presence`
  Estimated from the recent ratio of frames with a detected face.

The displayed state is not switched from a single frame. The analyzer keeps a
roughly 30-second sliding window, tracks low-score ratios and median score, and
maintains an `attentionDebt` value. Short posture changes only add limited
evidence; the state changes to `distracted` only after the evidence persists
and passes the state-machine hysteresis thresholds.

Posture is evaluated relative to the current source calibration. A
`calibrate_posture` control command samples stable MediaPipe frames for the
active camera, saves the median head pose, face position, face scale, and eye
openness under `focus_lab/config/sources/`, and immediately reloads the analyzer
so later scores measure deviation from that camera-specific baseline instead of
assuming a front-facing camera.

This keeps the state stable enough for a demoable edge-node prototype while still using landmark-based evidence from MediaPipe.

## Important local camera note

If all built-in local camera entries show `offline`, the backend is still healthy, but OpenCV cannot read a local webcam from this machine right now.

That usually means one of these:

- another app is holding the webcam
- the webcam is disabled in Windows privacy settings
- the webcam driver is not exposing a backend OpenCV can open
- this machine simply does not have a usable local webcam

In that case, the fastest path is usually to:

1. test another local camera index from the phone UI
2. use a network camera source instead
3. close apps like Teams, WeChat, QQ, Zoom, or camera utilities that may already own the webcam
