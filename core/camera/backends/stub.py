from __future__ import annotations

import base64

from core.camera.backends.base import CameraBackend, CameraFrame, FaceBox
from core.config import CameraConfig

_PLACEHOLDER_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/"
    "8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAGb/8QAFBAB"
    "AAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFB"
    "EBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAF"
    "BABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9k="
)
_PLACEHOLDER_BYTES = base64.b64decode(_PLACEHOLDER_JPEG_BASE64)


class StubCameraBackend(CameraBackend):
    name = "stub"

    def __init__(self, config: CameraConfig):
        self._config = config

    def is_available(self) -> bool:
        return True

    def capture_frame(self) -> CameraFrame:
        return CameraFrame(data=_PLACEHOLDER_BYTES, width=1, height=1, format="jpeg")

    def detect_faces(self, frame: CameraFrame) -> list[FaceBox]:
        return []
