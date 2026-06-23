from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import uvicorn


LOG_PATH = Path(__file__).with_name("run-server.err.log")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault("FOCUS_LOCAL_PROBE_COUNT", "1")
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:  # pragma: no cover
        LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
        raise
