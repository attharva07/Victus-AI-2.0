from __future__ import annotations

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/status")
async def notifications_status() -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Notification routes are not implemented in server-mode",
    )
