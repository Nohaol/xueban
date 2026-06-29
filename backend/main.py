from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .deepseek_client import DeepSeekAdvisor
from .engine import EngineConfig, FocusEngine
from .runtime_state import RuntimeStateStore, mask_secret
from .schemas import (
    AIReviewRequest,
    ControlCommand,
    McpEndpointConfig,
    NetworkSourceCreate,
    RuntimeSettings,
    SourceSelectionCommand,
    StudyStageCommand,
)
from .xiaozhi_bridge import ReminderStore
from .xiaozhi_mcp_runtime import (
    DEFAULT_RUNTIME_DIR,
    MCP_ENDPOINT_PREFIX,
    XiaozhiMcpRuntime,
)


app = FastAPI(title="Family Study Assistant Edge Node")
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUNTIME_DIR = Path(
    os.getenv("XUEBAN_RUNTIME_DIR", DEFAULT_RUNTIME_DIR)
).expanduser().resolve()
state_store = RuntimeStateStore(RUNTIME_DIR / "runtime_state.json")
reminder_store = ReminderStore(
    RUNTIME_DIR / "xiaozhi_reminders.json",
    state_store=state_store,
)
engine = FocusEngine(
    EngineConfig(),
    state_store=state_store,
    reminder_store=reminder_store,
)
mcp_runtime = XiaozhiMcpRuntime(
    state_store=state_store,
    runtime_dir=RUNTIME_DIR,
)
advisor = DeepSeekAdvisor()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    engine.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    try:
        mcp_runtime.stop()
    finally:
        engine.stop()


@app.get("/")
def parent_console() -> FileResponse:
    return FileResponse(STATIC_DIR / "parent-console.html")


@app.get("/v2")
def parent_console_v2() -> FileResponse:
    return FileResponse(STATIC_DIR / "parent-console-v2.html")


@app.get("/health")
def health() -> dict:
    payload = engine.get_payload()
    return {
        "ok": True,
        "status": payload["status"],
        "studentLabel": payload["studentLabel"],
    }


@app.get("/state")
def state() -> dict:
    return engine.get_payload()


@app.get("/settings")
def settings() -> dict:
    return engine.get_settings()


@app.post("/settings")
def update_settings(payload: RuntimeSettings) -> dict:
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    current = state_store.read()
    token = str(data.get("xiaozhiMcpToken") or "")
    current_token = str(current.get("xiaozhiMcpToken") or "")
    if token.startswith("***") or (
        current_token and token == mask_secret(current_token)
    ):
        token = current_token
        data["xiaozhiMcpToken"] = token
    url = str(data.get("xiaozhiMcpUrl") or "")
    if url or token:
        if url == MCP_ENDPOINT_PREFIX:
            endpoint = f"{url}{token}"
        elif url.startswith(MCP_ENDPOINT_PREFIX) and not token:
            endpoint = url
        else:
            endpoint = f"{url}{token}" if url.endswith("/") else f"{url}/{token}"
        try:
            mcp_runtime.configure(endpoint)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        data["xiaozhiMcpUrl"] = MCP_ENDPOINT_PREFIX
        data["xiaozhiMcpToken"] = endpoint[len(MCP_ENDPOINT_PREFIX) :]
    return engine.update_settings(data)


@app.get("/study-stage")
def get_study_stage() -> dict:
    return _stage_response(state_store.read())


@app.post("/study-stage")
def set_study_stage(payload: StudyStageCommand) -> dict:
    return _stage_response(state_store.set_stage(payload.stage, payload.source))


@app.get("/mcp/status")
def mcp_status() -> dict:
    return mcp_runtime.status()


@app.post("/mcp/config")
def configure_mcp(payload: McpEndpointConfig) -> dict:
    try:
        return mcp_runtime.configure(payload.endpoint)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/mcp/start")
def start_mcp() -> dict:
    try:
        return mcp_runtime.start()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/mcp/stop")
def stop_mcp() -> dict:
    return mcp_runtime.stop()


@app.get("/ai/advice")
def ai_advice(force: bool = False) -> dict:
    return advisor.advise(engine.get_payload(), force=force)


@app.post("/ai/review")
def ai_review(payload: AIReviewRequest, force: bool = False) -> dict:
    context = payload.context
    context.setdefault("current", engine.get_payload())
    return advisor.review(context, force=force)


@app.get("/sources")
def sources() -> dict:
    return {
        "items": engine.list_sources(),
        "current": engine.get_current_source(),
    }


@app.post("/sources/network")
def add_network_source(payload: NetworkSourceCreate) -> JSONResponse:
    source = engine.add_network_source(payload.label, payload.url, payload.transport)
    return JSONResponse(
        {
            "ok": True,
            "source": source,
            "items": engine.list_sources(),
        }
    )


@app.post("/sources/select")
def select_source(payload: SourceSelectionCommand) -> JSONResponse:
    try:
        current = engine.select_source(payload.sourceId)
    except KeyError:
        return JSONResponse({"ok": False, "error": "source_not_found"}, status_code=404)

    return JSONResponse(
        {
            "ok": True,
            "current": current,
            "items": engine.list_sources(),
        }
    )


@app.delete("/sources/{source_id}")
def delete_source(source_id: str) -> JSONResponse:
    try:
        current = engine.delete_source(source_id)
    except KeyError:
        return JSONResponse({"ok": False, "error": "source_not_found"}, status_code=404)
    except ValueError as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=400)

    return JSONResponse(
        {
            "ok": True,
            "current": current,
            "items": engine.list_sources(),
        }
    )


@app.get("/snapshot.jpg")
def snapshot() -> Response:
    return Response(content=engine.get_snapshot_bytes(), media_type="image/jpeg")


@app.get("/video_feed")
def video_feed() -> StreamingResponse:
    return StreamingResponse(
        engine.video_feed(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.post("/control")
def control(command: ControlCommand) -> JSONResponse:
    result = engine.handle_control(command.command, command.text)
    if command.text and command.command in {
        "parent_message",
        "ai_script_message",
        "managed_ai_reminder",
    }:
        result["reminder"] = reminder_store.enqueue(
            command.command,
            command.text,
            engine.get_payload(),
        )
    return JSONResponse(result)


@app.websocket("/ws")
async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(engine.get_payload())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


def _stage_response(state: dict) -> dict:
    return {
        "studyStage": state["studyStage"],
        "stageLabel": state["stageLabel"],
        "stageSource": state["stageSource"],
        "stageUpdatedAt": state["stageUpdatedAt"],
        "policy": state["policy"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
