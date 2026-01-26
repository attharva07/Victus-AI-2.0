from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import ServerSettings, get_settings
from .db import Database
from .rate_limit import RateLimiter
from .security import verify_access_token
from .routes import auth, finance, health, memory, me, notifications


def create_app(settings: ServerSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Victus Server", version=settings.version)
    app.state.settings = settings
    app.state.db = Database(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_window_seconds)

    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: Callable):
        request.state.user = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            payload = verify_access_token(token, settings.token_secret)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    user = app.state.db.get_user_by_id(user_id)
                    request.state.user = user
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(memory.router)
    app.include_router(finance.router)
    app.include_router(notifications.router)

    return app


app = create_app()
