from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import EngineConfig, FocusEngine
from .deepseek_client import DeepSeekAdvisor
from .schemas import ControlCommand, NetworkSourceCreate, SourceSelectionCommand


app = FastAPI(title="Family Study Assistant Edge Node")
engine = FocusEngine(EngineConfig())
advisor = DeepSeekAdvisor()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

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


@app.get("/ai/advice")
def ai_advice(force: bool = False) -> dict:
    return advisor.advise(engine.get_payload(), force=force)


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
    return JSONResponse(engine.handle_control(command.command, command.text))


@app.websocket("/ws")
async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(engine.get_payload())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
