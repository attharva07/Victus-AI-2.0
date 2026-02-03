from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CameraFrame:
    data: bytes
    width: int
    height: int
    format: str = "jpeg"


@dataclass(frozen=True)
class FaceBox:
    x: int
    y: int
    w: int
    h: int


class CameraBackend(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def capture_frame(self) -> CameraFrame:
        ...

    def detect_faces(self, frame: CameraFrame) -> list[FaceBox]:
        ...
