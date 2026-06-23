"""Scan camera indices 0-5 and report which ones work."""
import cv2

for index in range(6):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    ok, frame = cap.read()
    if ok and frame is not None:
        h, w = frame.shape[:2]
        print(f"camera {index}: ok, {w}x{h}")
    else:
        print(f"camera {index}: unavailable")
    cap.release()
