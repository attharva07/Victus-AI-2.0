from __future__ import annotations

from pydantic import BaseModel, Field


class CameraStatus(BaseModel):
    enabled: bool
    backend: str
    ok: bool
    message: str


class CaptureResponse(BaseModel):
    ok: bool
    enabled: bool
    backend: str
    capture_id: str | None = None
    stored: bool
    message: str


class RecognizeResponse(BaseModel):
    ok: bool
    enabled: bool
    backend: str
    matches: list[dict[str, str]] = Field(default_factory=list)
    message: str
