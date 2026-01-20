from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from victus.app import VictusApp
from victus.core.schemas import TurnEvent
from .admin_auth import AdminAuthManager
from .media_router import run_media_stop
from .memory_store_v2 import VictusMemory, VictusMemoryStore
from .policy_store import PolicyStore
from .turn_handler import TurnHandler
from .victus_adapter import build_victus_app

logger = logging.getLogger("victus_local")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


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
static_dir = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
victus_app = build_victus_app()
policy_store = PolicyStore()
victus_app.policy_engine.allowlist = policy_store.build_effective_allowlist()
admin_auth = AdminAuthManager()
memory_store_v2 = VictusMemoryStore()
turn_handler = TurnHandler(victus_app, memory_store_v2=memory_store_v2)


class TurnRequest(BaseModel):
    message: str


class MemoryRequest(BaseModel):
    id: Optional[str] = None
    type: str
    content: str
    source: str
    confidence: float = 0.7
    tags: list[str] = []
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    pinned: bool = False


class MemoryResponse(BaseModel):
    items: list[VictusMemory]


class MediaStopRequest(BaseModel):
    provider: str = "spotify"


class PolicyUpdateRequest(BaseModel):
    enabled_actions: list[str]


class AdminUnlockRequest(BaseModel):
    password: str


@app.on_event("startup")
async def startup_event() -> None:
    await log_hub.emit("info", "server_started", {"host": "127.0.0.1"})


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.post("/api/turn")
async def turn_endpoint(request: Request, payload: TurnRequest = Body(...)) -> StreamingResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    logger.info("TURN received: %s", message[:120])

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for event in turn_handler.run_turn(message):
                if await request.is_disconnected():
                    logger.info("Client disconnected; stopping turn.")
                    break
                await _forward_event_to_logs(event)
                data = json.dumps(_event_payload(event))
                yield f"event: {event.event}\ndata: {data}\n\n".encode("utf-8")
        except asyncio.CancelledError:
            logger.info("Turn stream cancelled.")
            raise
        except Exception as exc:  # noqa: BLE001
            error_event = TurnEvent(event="error", status="error", message=str(exc))
            await _forward_event_to_logs(error_event)
            data = json.dumps(_event_payload(error_event))
            yield f"event: {error_event.event}\ndata: {data}\n\n".encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/chat")
async def deprecated_chat_endpoint() -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={"error": "Deprecated endpoint. Use POST /api/turn (SSE)."},
    )


@app.get("/memory", response_model=MemoryResponse)
async def list_memory() -> MemoryResponse:
    return MemoryResponse(items=memory_store_v2.list())


@app.post("/memory", response_model=VictusMemory)
async def upsert_memory(payload: MemoryRequest = Body(...)) -> VictusMemory:
    data = payload.model_dump(exclude_none=True)
    if not data.get("created_at"):
        data["created_at"] = datetime.utcnow().isoformat() + "Z"
    memory = VictusMemory(**data)
    memory_store_v2.upsert(memory)
    return memory


@app.post("/api/media/stop")
async def media_stop(payload: MediaStopRequest = Body(...)) -> Dict[str, Any]:
    provider = payload.provider.strip().lower()
    result = run_media_stop(provider)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/policy")
async def get_policy(request: Request) -> Dict[str, Any]:
    token = request.cookies.get("victus_admin")
    state = policy_store.get_state()
    return {
        **state.as_response(),
        "admin": {"unlocked": admin_auth.is_session_valid(token)},
    }


@app.put("/api/policy")
async def update_policy(request: Request, payload: PolicyUpdateRequest = Body(...)) -> Dict[str, Any]:
    token = request.cookies.get("victus_admin")
    if not admin_auth.is_session_valid(token):
        raise HTTPException(status_code=401, detail="Admin access required.")
    state, enabled, disabled = policy_store.update_enabled_actions(payload.enabled_actions)
    victus_app.policy_engine.allowlist = policy_store.build_effective_allowlist()
    if enabled or disabled:
        logger.info("Policy updated. Enabled: %s Disabled: %s", enabled, disabled)
        await log_hub.emit(
            "info",
            "policy_update",
            {"enabled": enabled, "disabled": disabled, "updated_at": state.updated_at},
        )
    return state.as_response()


@app.post("/api/admin/unlock")
async def unlock_admin(payload: AdminUnlockRequest = Body(...)) -> JSONResponse:
    if not admin_auth.verify_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid admin password.")
    token, expires_at = admin_auth.issue_session()
    response = JSONResponse(
        status_code=200,
        content={"status": "unlocked", "expires_at": expires_at.isoformat() + "Z"},
    )
    response.set_cookie(
        "victus_admin",
        token,
        httponly=True,
        max_age=int(admin_auth.ttl.total_seconds()),
        samesite="lax",
    )
    return response


@app.post("/api/admin/lock")
async def lock_admin(request: Request) -> JSONResponse:
    token = request.cookies.get("victus_admin")
    admin_auth.revoke_session(token)
    response = JSONResponse(status_code=200, content={"status": "locked"})
    response.delete_cookie("victus_admin")
    return response


@app.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str) -> Dict[str, bool]:
    return {"deleted": memory_store_v2.delete(memory_id)}


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


@app.get("/api/routes")
async def list_routes() -> Dict[str, Any]:
    routes = []
    for route in app.routes:
        methods = sorted(getattr(route, "methods", []) or [])
        routes.append({"path": route.path, "methods": methods})
    return {"routes": routes}


def _event_payload(event: TurnEvent) -> Dict[str, Any]:
    return VictusApp._serialize_event(event)


async def _forward_event_to_logs(event: TurnEvent) -> None:
    if event.event == "status" and event.status:
        _log_status(event.status)
        await log_hub.emit("info", "status_update", {"status": event.status})
        return
    if event.event == "token":
        await log_hub.emit("info", "token", {"token": event.token})
        return
    if event.event == "tool_start":
        _log_tool_start(event.tool, event.action, event.args)
        await log_hub.emit(
            "info",
            "tool_start",
            {"tool": event.tool, "action": event.action, "args": event.args},
        )
        if event.action == "media_play":
            await log_hub.emit(
                "info",
                "media_start",
                {"provider": (event.args or {}).get("provider"), "query": (event.args or {}).get("query")},
            )
        return
    if event.event == "tool_done":
        _log_tool_done(event.tool, event.result)
        await log_hub.emit(
            "info",
            "tool_done",
            {"tool": event.tool, "action": event.action, "result": event.result},
        )
        if event.action == "open_app" and isinstance(event.result, dict):
            resolution = event.result.get("resolution")
            if isinstance(resolution, dict):
                await log_hub.emit(
                    "info",
                    "app_resolved",
                    {
                        "source": resolution.get("source"),
                        "alias": resolution.get("alias"),
                        "opened": event.result.get("opened"),
                    },
                )
            alias_learned = event.result.get("alias_learned")
            if isinstance(alias_learned, dict):
                await log_hub.emit(
                    "info",
                    "app_alias_learned",
                    {"alias": alias_learned.get("alias"), "target": alias_learned.get("target")},
                )
        if event.action == "media_play":
            result = event.result or {}
            if isinstance(result, dict) and result.get("error"):
                await log_hub.emit(
                    "error",
                    "media_error",
                    {"message": result.get("error"), "provider": result.get("provider")},
                )
            else:
                await log_hub.emit(
                    "info",
                    "media_done",
                    {
                        "provider": result.get("provider"),
                        "now_playing": result.get("now_playing"),
                        "confidence": result.get("confidence"),
                    },
                )
        return
    if event.event == "memory_used":
        await log_hub.emit("info", "memory_used", event.result or {})
        return
    if event.event == "memory_written":
        await log_hub.emit("info", "memory_written", event.result or {})
        return
    if event.event == "memory_candidate":
        await log_hub.emit("info", "memory_candidate", event.result or {})
        return
    if event.event == "error":
        _log_error(event.message or "")
        await log_hub.emit("error", "turn_error", {"message": event.message})
        return
    if event.event == "clarify":
        await log_hub.emit("info", "clarify", {"message": event.message})


def _log_status(status: str) -> None:
    if status == "thinking":
        logger.info("LLM: thinking")
    elif status == "executing":
        logger.info("LLM: executing")
    elif status == "done":
        logger.info("LLM: done")
    elif status == "error":
        logger.info("LLM: error")
    else:
        logger.info("LLM: %s", status)


def _log_tool_start(tool: Optional[str], action: Optional[str], args: Optional[Dict[str, Any]]) -> None:
    summary = _summarize_args(args)
    logger.info("TOOL start: %s %s %s", tool or "unknown", action or "unknown", summary)


def _log_tool_done(tool: Optional[str], result: Any) -> None:
    error = None
    if isinstance(result, dict):
        error = result.get("error")
    if error:
        logger.info("TOOL done: %s failed: %s", tool or "unknown", error)
    else:
        logger.info("TOOL done: %s ok", tool or "unknown")


def _log_error(message: str) -> None:
    normalized = message or "Unknown error"
    lowered = normalized.lower()
    if _is_ollama_memory_error(normalized):
        logger.error("LLM error: model requires more memory than available")
    elif lowered.startswith("unable to open app"):
        logger.error("Task error: %s", normalized)
    elif lowered.startswith("unable to open youtube"):
        logger.error("Task error: %s", normalized)
    else:
        logger.error("ERROR: %s", normalized)
    logger.error("LLM: error - %s", normalized)


def _summarize_args(args: Optional[Dict[str, Any]]) -> str:
    if not args:
        return ""
    try:
        summary = json.dumps(args, ensure_ascii=False)
    except TypeError:
        summary = str(args)
    if len(summary) > 120:
        summary = summary[:117] + "..."
    return summary


def _is_ollama_memory_error(message: str) -> bool:
    lowered = message.lower()
    return "requires more memory" in lowered or "requires more system memory" in lowered or "out of memory" in lowered
