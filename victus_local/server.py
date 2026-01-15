from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from victus.app import VictusApp
from victus.core.schemas import TurnEvent

from .victus_adapter import build_victus_app


class LogHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._sse_queues: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        await self.emit("info", "ui_connected", {"clients": len(self._clients)})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
        await self.emit("info", "ui_disconnected", {"clients": len(self._clients)})

    async def connect_sse(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._sse_queues.add(queue)
        return queue

    async def disconnect_sse(self, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._sse_queues.discard(queue)

    async def emit(self, level: str, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "level": level,
            "event": event,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        await self._broadcast(payload)

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        message = json.dumps(payload)
        async with self._lock:
            clients = list(self._clients)
            sse_queues = list(self._sse_queues)

        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_text(message)
            except WebSocketDisconnect:
                stale.append(client)
            except Exception:
                stale.append(client)

        if stale:
            async with self._lock:
                for client in stale:
                    self._clients.discard(client)

        for queue in sse_queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                continue


app = FastAPI()
log_hub = LogHub()
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
victus_app: VictusApp = build_victus_app()


class TurnRequest(BaseModel):
    message: str


@app.on_event("startup")
async def startup_event() -> None:
    await log_hub.emit("info", "server_started", {"host": "127.0.0.1"})


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.post("/api/turn")
async def turn_endpoint(payload: TurnRequest = Body(...)) -> StreamingResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for event in victus_app.run_request(message):
                await _forward_event_to_logs(event)
                data = json.dumps(_event_payload(event))
                yield f"data: {data}\n\n".encode("utf-8")
        except Exception as exc:  # noqa: BLE001
            error_event = TurnEvent(event="error", status="error", message=str(exc))
            await _forward_event_to_logs(error_event)
            data = json.dumps(_event_payload(error_event))
            yield f"data: {data}\n\n".encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.websocket("/ws/logs")
async def logs_websocket(websocket: WebSocket) -> None:
    await log_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await log_hub.disconnect(websocket)


@app.get("/api/logs/stream")
async def logs_stream() -> StreamingResponse:
    queue = await log_hub.connect_sse()

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            while True:
                message = await queue.get()
                yield f"data: {message}\n\n".encode("utf-8")
        finally:
            await log_hub.disconnect_sse(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _event_payload(event: TurnEvent) -> Dict[str, Any]:
    return VictusApp._serialize_event(event)


async def _forward_event_to_logs(event: TurnEvent) -> None:
    if event.event == "status" and event.status:
        await log_hub.emit("info", "status_update", {"status": event.status})
        return
    if event.event == "token":
        await log_hub.emit("info", "token", {"token": event.token})
        return
    if event.event == "tool_start":
        await log_hub.emit(
            "info",
            "tool_start",
            {"tool": event.tool, "action": event.action, "args": event.args},
        )
        return
    if event.event == "tool_done":
        await log_hub.emit(
            "info",
            "tool_done",
            {"tool": event.tool, "action": event.action, "result": event.result},
        )
        return
    if event.event == "error":
        await log_hub.emit("error", "turn_error", {"message": event.message})
        return
    if event.event == "clarify":
        await log_hub.emit("info", "clarify", {"message": event.message})
