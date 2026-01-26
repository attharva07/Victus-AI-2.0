from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from ..schemas import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    version = request.app.state.settings.version
    return HealthResponse(status="ok", version=version, time=datetime.now(timezone.utc).isoformat())
