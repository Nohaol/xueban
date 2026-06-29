from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.runtime_state import RuntimeStateStore
from backend.xiaozhi_bridge import ReminderStore
from backend.xiaozhi_mcp_runtime import (
    MCP_ENDPOINT_PREFIX,
    XiaozhiMcpRuntime,
    redact_endpoint,
    validate_endpoint,
)


class FakeProcess:
    def __init__(self, pid: int = 4321) -> None:
        self.pid = pid
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


@pytest.fixture(autouse=True)
def create_runtime_scripts(tmp_path):
    (tmp_path / "mcp_pipe.py").write_text("", encoding="utf-8")
    (tmp_path / "focus_reminder_mcp.py").write_text("", encoding="utf-8")


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://api.xiaozhi.me/mcp/token",
        "https://api.xiaozhi.me/mcp/token",
        "wss://evil.example/mcp/token",
        "wss://api.xiaozhi.me/other/token",
        " wss://api.xiaozhi.me/mcp/token",
    ],
)
def test_endpoint_validation_rejects_noncanonical_urls(endpoint):
    with pytest.raises(ValueError, match="invalid_xiaozhi_mcp_endpoint"):
        validate_endpoint(endpoint)


def test_endpoint_validation_accepts_only_nonempty_token_suffix():
    endpoint = f"{MCP_ENDPOINT_PREFIX}abc123"

    assert validate_endpoint(endpoint) == endpoint
    with pytest.raises(ValueError, match="invalid_xiaozhi_mcp_endpoint"):
        validate_endpoint(MCP_ENDPOINT_PREFIX)


def test_endpoint_redaction_never_returns_complete_token():
    endpoint = f"{MCP_ENDPOINT_PREFIX}super-secret-token"

    redacted = redact_endpoint(endpoint)

    assert redacted.startswith(MCP_ENDPOINT_PREFIX)
    assert "super-secret-token" not in redacted
    assert redacted.endswith("en")


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("short", "*****"),
        ("abcdefghijk", "ab*******jk"),
    ],
)
def test_endpoint_redaction_uses_safe_mask_for_every_token_length(
    token,
    expected,
):
    assert redact_endpoint(f"{MCP_ENDPOINT_PREFIX}{token}") == (
        f"{MCP_ENDPOINT_PREFIX}{expected}"
    )


def test_runtime_starts_with_current_python_and_redacts_status(tmp_path):
    endpoint = f"{MCP_ENDPOINT_PREFIX}super-secret-token"
    state = RuntimeStateStore(tmp_path / "state.json")
    calls = []
    process = FakeProcess()

    def process_factory(command, **kwargs):
        calls.append((command, kwargs))
        return process

    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=process_factory,
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.configure(endpoint)
    started = runtime.start()

    command, kwargs = calls[0]
    assert command[0] == sys.executable
    assert endpoint not in command
    assert kwargs["env"]["MCP_ENDPOINT"] == endpoint
    assert started["running"] is True
    assert started["pid"] == process.pid
    assert endpoint not in repr(started)
    assert "super-secret-token" not in repr(runtime.status())
    persisted = state.read()
    assert persisted["xiaozhiMcpUrl"] == MCP_ENDPOINT_PREFIX
    assert persisted["xiaozhiMcpToken"] == "super-secret-token"


def test_runtime_stop_only_terminates_owned_matching_process(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    process = FakeProcess(pid=88)
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=lambda *args, **kwargs: process,
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")
    runtime.start()

    runtime._owned_pid = 99
    refused = runtime.stop()

    assert refused["stopped"] is False
    assert refused["error"] == "mcp_process_not_owned"
    assert process.terminated is False

    runtime._owned_pid = process.pid
    stopped = runtime.stop()
    assert stopped["stopped"] is True
    assert process.terminated is True


def test_concurrent_start_creates_only_one_process(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    calls = []
    calls_lock = threading.Lock()

    def process_factory(*args, **kwargs):
        with calls_lock:
            pid = 5000 + len(calls)
            calls.append(pid)
        time.sleep(0.05)
        return FakeProcess(pid=pid)

    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=process_factory,
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: runtime.start(), range(8)))

    assert len(calls) == 1
    assert all(result["running"] is True for result in results)


def test_start_rolls_back_and_terminates_when_pid_persistence_fails(
    tmp_path,
    monkeypatch,
):
    state = RuntimeStateStore(tmp_path / "state.json")
    process = FakeProcess(pid=6111)
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=lambda *args, **kwargs: process,
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")

    def fail_pid_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(runtime, "_write_pid_record", fail_pid_write, raising=False)

    with pytest.raises(OSError, match="disk full"):
        runtime.start()

    assert process.terminated is True
    assert runtime._process is None
    assert runtime._owned_pid is None


def test_pid_and_status_files_are_atomic_owned_json(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=lambda *args, **kwargs: FakeProcess(pid=7331),
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")
    runtime.start()

    pid_record = json.loads(runtime.pid_path.read_text(encoding="utf-8"))
    status_record = json.loads(runtime.status_path.read_text(encoding="utf-8"))

    assert pid_record["pid"] == 7331
    assert pid_record["instanceId"] == runtime.instance_id
    assert status_record["pid"] == 7331
    assert status_record["instanceId"] == runtime.instance_id
    assert not list((tmp_path / "runtime").glob("*.tmp"))


def test_stale_pid_without_owned_instance_is_never_terminated(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=lambda *args, **kwargs: FakeProcess(pid=8001),
        pipe_script=tmp_path / "mcp_pipe.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.runtime_dir.mkdir(parents=True)
    runtime.pid_path.write_text(
        json.dumps({"pid": 4, "instanceId": "some-other-service"}),
        encoding="utf-8",
    )

    result = runtime.stop()

    assert result["stopped"] is False
    assert result["error"] == "mcp_process_not_owned"


def test_runtime_resolves_paths_and_passes_absolute_runtime_dir(
    tmp_path,
    monkeypatch,
):
    first_cwd = tmp_path / "first"
    second_cwd = tmp_path / "second"
    first_cwd.mkdir()
    second_cwd.mkdir()
    pipe_script = first_cwd / "pipe.py"
    tool_script = first_cwd / "tool.py"
    pipe_script.write_text("", encoding="utf-8")
    tool_script.write_text("", encoding="utf-8")
    calls = []

    monkeypatch.chdir(first_cwd)
    state = RuntimeStateStore("shared/runtime_state.json")
    reminders = ReminderStore(
        "shared/xiaozhi_reminders.json",
        state_store=state,
    )
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir="shared",
        process_factory=lambda command, **kwargs: (
            calls.append((command, kwargs)) or FakeProcess()
        ),
        pipe_script="pipe.py",
        tool_script="tool.py",
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")
    reminders.enqueue("managed_ai_reminder", "keep going")
    runtime.start()

    assert runtime.runtime_dir == (first_cwd / "shared").resolve()
    assert runtime.pipe_script == pipe_script.resolve()
    assert runtime.tool_script == tool_script.resolve()
    assert Path(calls[0][1]["env"]["XUEBAN_RUNTIME_DIR"]).is_absolute()

    monkeypatch.chdir(second_cwd)
    shared_state = RuntimeStateStore(runtime.runtime_dir / "runtime_state.json")
    shared_reminders = ReminderStore(
        runtime.runtime_dir / "xiaozhi_reminders.json",
        state_store=shared_state,
    )
    assert shared_state.read()["xiaozhiMcpToken"] == "token"
    assert shared_reminders.snapshot()["pendingCount"] == 1


def test_pipe_script_environment_override_and_missing_error(tmp_path, monkeypatch):
    missing_pipe = tmp_path / "missing" / "mcp_pipe.py"
    tool_script = tmp_path / "focus_reminder_mcp.py"
    tool_script.write_text("", encoding="utf-8")
    monkeypatch.setenv("XUEBAN_MCP_PIPE_SCRIPT", str(missing_pipe))
    state = RuntimeStateStore(tmp_path / "state.json")
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        tool_script=tool_script,
    )
    runtime.process_factory = lambda *args, **kwargs: pytest.fail(
        "missing bridge script must not spawn a process"
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")

    result = runtime.start()

    assert runtime.pipe_script == missing_pipe.resolve()
    assert result["ok"] is False
    assert result["error"] == "bridge_script_missing"


def test_missing_bridge_script_never_calls_custom_process_factory(tmp_path):
    calls = []
    state = RuntimeStateStore(tmp_path / "state.json")
    runtime = XiaozhiMcpRuntime(
        state_store=state,
        runtime_dir=tmp_path / "runtime",
        process_factory=lambda *args, **kwargs: calls.append(args),
        pipe_script=tmp_path / "does-not-exist.py",
        tool_script=tmp_path / "focus_reminder_mcp.py",
    )
    runtime.configure(f"{MCP_ENDPOINT_PREFIX}token")

    result = runtime.start()

    assert result["ok"] is False
    assert result["error"] == "bridge_script_missing"
    assert calls == []


def test_main_resolves_relative_runtime_dir_at_import(tmp_path):
    cwd = tmp_path / "service-cwd"
    cwd.mkdir()
    project_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_dir)
    env["XUEBAN_RUNTIME_DIR"] = "shared-runtime"

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.main import RUNTIME_DIR; print(RUNTIME_DIR)",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    assert completed.stdout.strip().splitlines()[-1] == str(
        (cwd / "shared-runtime").resolve()
    )
