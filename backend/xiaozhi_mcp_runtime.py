from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .runtime_state import RuntimeStateStore, mask_secret


MCP_ENDPOINT_PREFIX = "wss://api.xiaozhi.me/mcp/"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
DEFAULT_RUNTIME_DIR = BASE_DIR / "runtime"
DEFAULT_PIPE_SCRIPT = WORKSPACE_DIR / "mcp-calculator-main" / "mcp_pipe.py"
DEFAULT_TOOL_SCRIPT = PROJECT_DIR / "xiaozhi_bridge" / "focus_reminder_mcp.py"


def validate_endpoint(endpoint: str) -> str:
    value = str(endpoint or "")
    suffix = value[len(MCP_ENDPOINT_PREFIX) :] if value.startswith(MCP_ENDPOINT_PREFIX) else ""
    if (
        not suffix
        or value != value.strip()
        or any(char.isspace() for char in value)
    ):
        raise ValueError("invalid_xiaozhi_mcp_endpoint")
    return value


def redact_endpoint(endpoint: str) -> str:
    if not endpoint:
        return ""
    try:
        value = validate_endpoint(endpoint)
    except ValueError:
        return "[invalid endpoint]"
    token = value[len(MCP_ENDPOINT_PREFIX) :]
    return f"{MCP_ENDPOINT_PREFIX}{mask_secret(token)}"


class XiaozhiMcpRuntime:
    def __init__(
        self,
        *,
        state_store: RuntimeStateStore,
        runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
        process_factory: Callable[..., Any] = subprocess.Popen,
        pipe_script: str | Path | None = None,
        tool_script: str | Path = DEFAULT_TOOL_SCRIPT,
    ) -> None:
        self.state_store = state_store
        self.runtime_dir = Path(runtime_dir).expanduser().resolve()
        self.process_factory = process_factory
        selected_pipe_script = pipe_script or os.getenv(
            "XUEBAN_MCP_PIPE_SCRIPT",
            DEFAULT_PIPE_SCRIPT,
        )
        self.pipe_script = Path(selected_pipe_script).expanduser().resolve()
        self.tool_script = Path(tool_script).expanduser().resolve()
        self.pid_path = self.runtime_dir / "xiaozhi_mcp.pid"
        self.status_path = self.runtime_dir / "xiaozhi_mcp_status.json"
        self.log_path = self.runtime_dir / "xiaozhi_mcp_runtime.log"
        self.instance_id = uuid.uuid4().hex
        self._lock = threading.RLock()
        self._process = None
        self._owned_pid: int | None = None
        self._uses_default_process_factory = process_factory is subprocess.Popen

    def configure(self, endpoint: str) -> dict:
        with self._lock:
            value = validate_endpoint(endpoint)
            token = value[len(MCP_ENDPOINT_PREFIX) :]
            self.state_store.update(
                {
                    "xiaozhiMcpUrl": MCP_ENDPOINT_PREFIX,
                    "xiaozhiMcpToken": token,
                }
            )
            self._log("configuration updated")
            return self.status()

    def status(self) -> dict:
        with self._lock:
            endpoint = self._configured_endpoint(raise_on_invalid=False)
            running = bool(
                self._process is not None
                and self._owned_pid == getattr(self._process, "pid", None)
                and self._process.poll() is None
            )
            result = {
                "configured": bool(endpoint),
                "endpointPreview": redact_endpoint(endpoint),
                "running": running,
                "pid": self._owned_pid if running else None,
                "instanceId": self.instance_id,
            }
            self._write_status(result)
            return result

    def start(self) -> dict:
        with self._lock:
            endpoint = self._configured_endpoint()
            if self._process is not None and self._process.poll() is None:
                return {"ok": True, "message": "already_running", **self.status()}
            if not self.pipe_script.is_file() or not self.tool_script.is_file():
                return {
                    "ok": False,
                    "error": "bridge_script_missing",
                    **self.status(),
                }

            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["MCP_ENDPOINT"] = endpoint
            env["XUEBAN_RUNTIME_DIR"] = str(self.runtime_dir)
            env["XUEBAN_MCP_INSTANCE_ID"] = self.instance_id
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            command = [
                sys.executable,
                str(self.pipe_script),
                str(self.tool_script),
            ]
            process = self.process_factory(
                command,
                cwd=str(self.pipe_script.parent),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            self._process = process
            self._owned_pid = int(process.pid)
            try:
                self._write_pid_record()
                self._log(f"bridge started pid={self._owned_pid}")
                result = {"ok": True, "message": "started", **self.status()}
            except Exception:
                self._rollback_started_process(process)
                raise
            return result

    def stop(self) -> dict:
        with self._lock:
            process = self._process
            process_pid = getattr(process, "pid", None)
            record = self._read_pid_record()
            record_is_owned = bool(
                record
                and record.get("pid") == self._owned_pid
                and record.get("instanceId") == self.instance_id
            )
            if (
                process is None
                or self._owned_pid is None
                or process_pid != self._owned_pid
                or not record_is_owned
            ):
                return {
                    "stopped": False,
                    "error": "mcp_process_not_owned",
                    **self.status(),
                }

            if process.poll() is None:
                self._terminate(process)
            stopped_pid = self._owned_pid
            self._process = None
            self._owned_pid = None
            self.pid_path.unlink(missing_ok=True)
            self._log(f"bridge stopped pid={stopped_pid}")
            return {"ok": True, "stopped": True, **self.status()}

    def _configured_endpoint(self, *, raise_on_invalid: bool = True) -> str:
        state = self.state_store.read()
        url = str(state.get("xiaozhiMcpUrl") or "")
        token = str(state.get("xiaozhiMcpToken") or "")
        if token:
            endpoint = f"{url}{token}" if url.endswith("/") else f"{url}/{token}"
        else:
            endpoint = url
        if not endpoint:
            if raise_on_invalid:
                raise ValueError("missing_xiaozhi_mcp_endpoint")
            return ""
        try:
            return validate_endpoint(endpoint)
        except ValueError:
            if raise_on_invalid:
                raise
            return ""

    def _terminate(self, process: Any) -> None:
        if os.name == "nt" and self._uses_default_process_factory:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def _read_pid(self) -> int | None:
        record = self._read_pid_record()
        return int(record["pid"]) if record else None

    def _read_pid_record(self) -> dict | None:
        try:
            value = json.loads(self.pid_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if isinstance(value, int):
            return {"pid": value, "instanceId": None}
        if (
            isinstance(value, dict)
            and isinstance(value.get("pid"), int)
            and isinstance(value.get("instanceId"), str)
        ):
            return value
        return None

    def _write_pid_record(self) -> None:
        self._atomic_write_text(
            self.pid_path,
            json.dumps(
                {
                    "pid": self._owned_pid,
                    "instanceId": self.instance_id,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _write_status(self, status: dict) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        public_status = {
            "configured": bool(status.get("configured")),
            "endpointPreview": str(status.get("endpointPreview") or ""),
            "running": bool(status.get("running")),
            "pid": status.get("pid"),
            "instanceId": self.instance_id,
            "updatedAt": int(time.time() * 1000),
        }
        self._atomic_write_text(
            self.status_path,
            json.dumps(public_status, ensure_ascii=False, indent=2),
        )

    def _atomic_write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _rollback_started_process(self, process: Any) -> None:
        try:
            if process.poll() is None:
                self._terminate(process)
        finally:
            self._process = None
            self._owned_pid = None
            record = self._read_pid_record()
            if record and record.get("instanceId") == self.instance_id:
                self.pid_path.unlink(missing_ok=True)
            self.status_path.unlink(missing_ok=True)

    def _log(self, message: str) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{int(time.time() * 1000)} {message}\n")
