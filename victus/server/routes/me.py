from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from ..schemas import UserResponse


router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(request: Request) -> UserResponse:
    user = request.state.user
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return UserResponse(
        id=user.user_id,
        email=user.email,
        is_admin=user.is_admin,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
    )
