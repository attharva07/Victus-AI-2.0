from __future__ import annotations

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from adapters.llm.provider import LLMProvider
from core.config import ensure_directories
from core.logging.audit import audit_event
from core.logging.logger import get_logger
from core.orchestrator.router import route_intent
from core.orchestrator.schemas import OrchestrateRequest, OrchestrateResponse
from core.security.auth import login_user, require_user


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_app() -> FastAPI:
    ensure_directories()
    get_logger()
    app = FastAPI(title="Victus Local")
    llm_provider = LLMProvider()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/login", response_model=LoginResponse)
    def login(payload: LoginRequest) -> LoginResponse:
        token = login_user(payload.username, payload.password)
        return LoginResponse(access_token=token)

    @app.get("/me")
    def me(user: str = Depends(require_user)) -> dict[str, str]:
        return {"username": user}

    @app.post("/orchestrate", response_model=OrchestrateResponse)
    def orchestrate(
        payload: OrchestrateRequest, user: str = Depends(require_user)
    ) -> OrchestrateResponse:
        audit_event("orchestrate_requested", username=user, utterance=payload.utterance)
        return route_intent(payload, llm_provider)

    return app


app = create_app()
