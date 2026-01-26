from __future__ import annotations

from fastapi import APIRouter, HTTPException, status


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/status")
async def memory_status() -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Memory routes are not implemented in server-mode")
