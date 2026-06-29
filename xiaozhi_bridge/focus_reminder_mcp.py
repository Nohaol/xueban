from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from fastmcp import FastMCP
from filelock import FileLock


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend.runtime_state import RuntimeStateStore  # noqa: E402
from backend.xiaozhi_bridge import ReminderStore  # noqa: E402


RUNTIME_DIR = Path(
    os.getenv("XUEBAN_RUNTIME_DIR", PROJECT_DIR / "backend" / "runtime")
)
state_store = RuntimeStateStore(RUNTIME_DIR / "runtime_state.json")
reminder_store = ReminderStore(
    RUNTIME_DIR / "xiaozhi_reminders.json",
    state_store=state_store,
)
CALL_LOG_PATH = RUNTIME_DIR / "xiaozhi_mcp_calls.jsonl"
call_log_lock = FileLock(f"{CALL_LOG_PATH}.lock")
mcp = FastMCP("XiaozhiStudyCompanion")


def _stage_response(state: dict) -> dict:
    return {
        "studyStage": state["studyStage"],
        "stageLabel": state["stageLabel"],
        "stageSource": state["stageSource"],
        "stageUpdatedAt": state["stageUpdatedAt"],
        "policy": state["policy"],
    }


def _queue_result_summary(result: dict) -> dict:
    summary = {
        key: result[key]
        for key in (
            "hasReminder",
            "reminderId",
            "acknowledged",
            "success",
            "error",
            "pendingCount",
            "deliveredCount",
            "completedCount",
        )
        if key in result
    }
    item = result.get("item")
    if isinstance(item, dict):
        summary["item"] = {
            key: item[key]
            for key in (
                "id",
                "command",
                "studyStage",
                "stageLabel",
                "policyVersion",
                "status",
                "spoken",
            )
            if key in item
        }
    else:
        for key in (
            "command",
            "studyStage",
            "stageLabel",
            "policyVersion",
            "status",
        ):
            if key in result:
                summary[key] = result[key]
    return summary


def _write_call_log(tool: str, request: dict, result: dict) -> None:
    record = {
        "timestamp": int(time.time() * 1000),
        "tool": tool,
        "request": request,
        "result": result,
    }
    CALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with call_log_lock:
        with CALL_LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _try_write_call_log(tool: str, request: dict, result: dict) -> None:
    try:
        _write_call_log(tool, request, result)
    except Exception:
        return


def set_study_stage(stage: str, source: str = "voice") -> dict:
    """Set and persist the current school stage selected during conversation."""
    try:
        result = _stage_response(state_store.set_stage(stage, source))
    except ValueError as error:
        error_code = str(error)
        if error_code not in {"invalid_stage_source", "invalid_study_stage"}:
            error_code = "invalid_stage_request"
        _try_write_call_log(
            "set_study_stage",
            {},
            {"success": False, "error": error_code},
        )
        raise
    except Exception:
        _try_write_call_log(
            "set_study_stage",
            {},
            {"success": False, "error": "stage_update_failed"},
        )
        raise
    request = {
        "stage": result["studyStage"],
        "source": result["stageSource"],
    }
    _try_write_call_log("set_study_stage", request, result)
    return result


def get_study_stage() -> dict:
    """Return the persisted school stage and its reminder policy."""
    result = _stage_response(state_store.read())
    _try_write_call_log("get_study_stage", {}, result)
    return result


def check_study_focus_and_remind_child() -> dict:
    """Claim the next reminder. Speak reminderText only when hasReminder is true."""
    result = reminder_store.pop_next()
    _try_write_call_log(
        "check_study_focus_and_remind_child",
        {},
        _queue_result_summary(result),
    )
    return result


def mark_study_reminder_spoken(
    reminder_id: str,
    spoken: bool = True,
) -> dict:
    """Acknowledge a claimed reminder after it was spoken or dismissed."""
    request = {"reminderId": reminder_id, "spoken": bool(spoken)}
    result = reminder_store.acknowledge(reminder_id, spoken)
    _try_write_call_log(
        "mark_study_reminder_spoken",
        request,
        _queue_result_summary(result),
    )
    return result


def inspect_study_reminder_queue() -> dict:
    """Inspect reminder counts and items without claiming a pending reminder."""
    result = reminder_store.snapshot()
    _try_write_call_log(
        "inspect_study_reminder_queue",
        {},
        _queue_result_summary(result),
    )
    return result


for tool in (
    set_study_stage,
    get_study_stage,
    check_study_focus_and_remind_child,
    mark_study_reminder_spoken,
    inspect_study_reminder_queue,
):
    mcp.tool()(tool)


if __name__ == "__main__":
    mcp.run(transport="stdio")
