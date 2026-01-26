from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    time: str


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str
    totp: str | None = None


class TokenResponse(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool
    mfa_enabled: bool
    created_at: str


class MFAEnrollResponse(BaseModel):
    secret: str
    otpauth_url: str


class MFAVerifyRequest(BaseModel):
    code: str
