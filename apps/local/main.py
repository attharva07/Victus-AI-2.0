from __future__ import annotations

import base64
import secrets

import bcrypt
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel

from adapters.llm.provider import LLMProvider
from core.camera.models import CameraStatus, CaptureResponse, RecognizeResponse
from core.camera.service import CameraService
from core.config import ensure_directories
from core.filesystem.sandbox import FileSandboxError
from core.filesystem.service import list_sandbox_files, read_sandbox_file, write_sandbox_file
from core.finance.service import add_transaction, list_transactions, summary
from core.logging.audit import audit_event, safe_excerpt, text_hash
from core.logging.logger import get_logger
from core.memory.service import add_memory, delete_memory, list_recent, search_memories
from core.orchestrator.router import route_intent
from core.orchestrator.schemas import OrchestrateErrorResponse, OrchestrateRequest, OrchestrateResponse
from core.security.auth import login_user, require_user
from core.security.bootstrap_store import is_bootstrapped, set_bootstrap


class LoginRequest(BaseModel):
    username: str
    password: str


class BootstrapInitRequest(BaseModel):
    username: str
    password: str


class BootstrapInitResponse(BaseModel):
    ok: bool
    bootstrapped: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MemoryAddRequest(BaseModel):
    content: str
    type: str = "note"
    tags: list[str] | None = None
    importance: int = 5
    confidence: float = 0.8


class FinanceAddRequest(BaseModel):
    amount: float
    currency: str = "USD"
    category: str
    merchant: str | None = None
    note: str | None = None
    method: str | None = None


class FileWriteRequest(BaseModel):
    path: str
    content: str
    mode: str = "overwrite"


class CameraCaptureRequest(BaseModel):
    reason: str | None = None
    format: str = "jpg"


class CameraRecognizeRequest(BaseModel):
    capture_id: str | None = None
    image_b64: str | None = None


def _request_id(request: Request) -> str | None:
    return request.headers.get("X-Request-ID") or request.headers.get("X-Request-Id")


def create_app() -> FastAPI:
    ensure_directories()
    get_logger()
    app = FastAPI(title="Victus Local")
    llm_provider = LLMProvider()
    camera_service = CameraService()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/login", response_model=LoginResponse)
    def login(payload: LoginRequest) -> LoginResponse:
        token = login_user(payload.username, payload.password)
        return LoginResponse(access_token=token)

    @app.get("/bootstrap/status")
    def bootstrap_status() -> dict[str, bool]:
        return {"bootstrapped": is_bootstrapped()}

    @app.post("/bootstrap/init", response_model=BootstrapInitResponse)
    def bootstrap_init(payload: BootstrapInitRequest, request: Request) -> BootstrapInitResponse:
        request_id = _request_id(request)
        if is_bootstrapped():
            audit_event("bootstrap_init", ok=False, request_id=request_id, reason="already_bootstrapped")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "already_bootstrapped",
                    "message": "Victus Local has already been bootstrapped.",
                },
            )
        if payload.username != "admin":
            audit_event("bootstrap_init", ok=False, request_id=request_id, reason="invalid_username")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_username", "message": "Only the 'admin' username is allowed."},
            )
        if len(payload.password) < 12:
            audit_event("bootstrap_init", ok=False, request_id=request_id, reason="weak_password")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "weak_password", "message": "Password must be at least 12 characters."},
            )

        password_hash = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        secret_bytes = secrets.token_bytes(32)
        jwt_secret = base64.urlsafe_b64encode(secret_bytes).decode("utf-8")
        set_bootstrap(password_hash, jwt_secret)
        audit_event("bootstrap_init", ok=True, request_id=request_id, username=payload.username)
        return BootstrapInitResponse(ok=True, bootstrapped=True)

    @app.get("/me")
    def me(user: str = Depends(require_user)) -> dict[str, str]:
        return {"username": user}

    @app.post(
        "/orchestrate",
        response_model=OrchestrateResponse | OrchestrateErrorResponse,
        responses={200: {"model": OrchestrateErrorResponse}},
    )
    def orchestrate(
        payload: OrchestrateRequest, user: str = Depends(require_user)
    ) -> OrchestrateResponse | OrchestrateErrorResponse:
        user_text = payload.normalized_text()
        audit_event(
            "orchestrate_requested",
            username=user,
            text_hash=text_hash(user_text),
            text_excerpt=safe_excerpt(user_text),
        )
        return route_intent(payload, llm_provider)

    @app.post("/memory/add")
    def memory_add(payload: MemoryAddRequest, user: str = Depends(require_user)) -> dict[str, str]:
        memory_id = add_memory(
            content=payload.content,
            type=payload.type,
            tags=payload.tags,
            source=user,
            importance=payload.importance,
            confidence=payload.confidence,
        )
        return {"id": memory_id}

    @app.get("/memory/search")
    def memory_search(
        q: str = Query(..., alias="q"),
        tag: list[str] | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=100),
        user: str = Depends(require_user),
    ) -> dict[str, object]:
        results = search_memories(query=q, tags=tag, limit=limit)
        return {"results": results}

    @app.get("/memory/list")
    def memory_list(
        limit: int = Query(default=20, ge=1, le=100),
        user: str = Depends(require_user),
    ) -> dict[str, object]:
        results = list_recent(limit=limit)
        return {"results": results}

    @app.delete("/memory/{memory_id}")
    def memory_delete(memory_id: str, user: str = Depends(require_user)) -> dict[str, bool]:
        deleted = delete_memory(memory_id)
        return {"deleted": deleted}

    @app.post("/finance/add")
    def finance_add(payload: FinanceAddRequest, user: str = Depends(require_user)) -> dict[str, str]:
        amount_cents = int(round(payload.amount * 100))
        transaction_id = add_transaction(
            amount_cents=amount_cents,
            currency=payload.currency,
            category=payload.category,
            merchant=payload.merchant,
            note=payload.note,
            method=payload.method,
            source=user,
        )
        return {"id": transaction_id}

    @app.get("/finance/list")
    def finance_list(
        category: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        user: str = Depends(require_user),
    ) -> dict[str, object]:
        results = list_transactions(category=category, limit=limit)
        return {"results": results}

    @app.get("/finance/summary")
    def finance_summary(
        period: str = Query(default="week"),
        start_ts: str | None = Query(default=None),
        end_ts: str | None = Query(default=None),
        user: str = Depends(require_user),
    ) -> dict[str, object]:
        report = summary(period=period, start_ts=start_ts, end_ts=end_ts, group_by="category")
        return {"report": report}

    @app.get("/files/list")
    def files_list(user: str = Depends(require_user)) -> dict[str, object]:
        files = list_sandbox_files()
        return {"files": files}

    @app.get("/files/read")
    def files_read(path: str = Query(...), user: str = Depends(require_user)) -> dict[str, object]:
        try:
            content = read_sandbox_file(path)
        except FileSandboxError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {"content": content}

    @app.post("/files/write")
    def files_write(payload: FileWriteRequest, user: str = Depends(require_user)) -> dict[str, bool]:
        try:
            write_sandbox_file(payload.path, payload.content, payload.mode)
        except FileSandboxError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {"ok": True}

    @app.get("/camera/status", response_model=CameraStatus)
    def camera_status(request: Request, user: str = Depends(require_user)) -> CameraStatus:
        request_id = _request_id(request)
        return camera_service.status(request_id=request_id)

    @app.post("/camera/capture", response_model=CaptureResponse)
    def camera_capture(
        request: Request,
        payload: CameraCaptureRequest = Body(default_factory=CameraCaptureRequest),
        user: str = Depends(require_user),
    ) -> CaptureResponse:
        request_id = _request_id(request)
        return camera_service.capture(
            request_id=request_id, reason=payload.reason, format=payload.format
        )

    @app.post("/camera/recognize", response_model=RecognizeResponse)
    def camera_recognize(
        request: Request,
        payload: CameraRecognizeRequest = Body(default_factory=CameraRecognizeRequest),
        user: str = Depends(require_user),
    ) -> RecognizeResponse:
        request_id = _request_id(request)
        return camera_service.recognize(
            request_id=request_id,
            capture_id=payload.capture_id,
            image_b64=payload.image_b64,
        )

    return app


app = create_app()
