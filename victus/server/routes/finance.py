from __future__ import annotations

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/status")
async def finance_status() -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Finance routes are not implemented in server-mode")
