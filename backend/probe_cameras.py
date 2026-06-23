from __future__ import annotations

import argparse
from pathlib import Path

import cv2


BACKENDS = [
    ("CAP_ANY", cv2.CAP_ANY),
    ("CAP_DSHOW", cv2.CAP_DSHOW),
    ("CAP_MSMF", cv2.CAP_MSMF),
]


def probe_index(index: int) -> list[tuple[str, bool, bool, tuple[int, int, int] | None]]:
    results: list[tuple[str, bool, bool, tuple[int, int, int] | None]] = []
    for backend_name, backend_id in BACKENDS:
        capture = cv2.VideoCapture(index, backend_id)
        opened = capture.isOpened()
        read_ok = False
        shape = None
        if opened:
            read_ok, frame = capture.read()
            if read_ok and frame is not None:
                shape = tuple(frame.shape)
        capture.release()
        results.append((backend_name, opened, read_ok, shape))
    return results


def save_first_frame(max_index: int, output: Path) -> bool:
    for index in range(max_index + 1):
        for _, backend_id in BACKENDS:
            capture = cv2.VideoCapture(index, backend_id)
            if not capture.isOpened():
                capture.release()
                continue
            read_ok, frame = capture.read()
            capture.release()
            if read_ok and frame is not None:
                cv2.imwrite(str(output), frame)
                return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local cameras on Windows.")
    parser.add_argument("--max-index", type=int, default=15, help="highest local camera index to probe")
    parser.add_argument(
        "--save-frame",
        action="store_true",
        help="save the first successfully captured frame to backend/probe_snapshot.jpg",
    )
    args = parser.parse_args()

    print(f"OpenCV: {cv2.__version__}")
    any_success = False

    for index in range(args.max_index + 1):
        print(f"\nindex {index}")
        for backend_name, opened, read_ok, shape in probe_index(index):
            print(
                f"  {backend_name:<10} opened={str(opened):<5} "
                f"read={str(read_ok):<5} shape={shape}"
            )
            if opened or read_ok:
                any_success = True

    if not any_success:
        print("\nNo local camera opened successfully in this Python environment.")
    else:
        print("\nAt least one local camera opened successfully.")

    if args.save_frame:
        output = Path(__file__).resolve().parent / "probe_snapshot.jpg"
        if save_first_frame(args.max_index, output):
            print(f"Saved first frame to: {output}")
        else:
            print("Could not save a frame because no camera returned an image.")


if __name__ == "__main__":
    main()
