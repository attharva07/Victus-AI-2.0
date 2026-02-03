from __future__ import annotations

from pydantic import BaseModel, Field


class CameraStatus(BaseModel):
    enabled: bool
    backend: str
    available: bool
    message: str


class CaptureResponse(BaseModel):
    captured: bool
    width: int | None = None
    height: int | None = None
    format: str | None = None
    image_base64: str | None = None


class FaceBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class RecognizeResponse(BaseModel):
    faces_detected: int
    boxes: list[FaceBox] = Field(default_factory=list)
    confidence: float | None = None
