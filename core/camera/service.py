from __future__ import annotations

import base64

from core.camera.backends.base import CameraBackend
from core.camera.backends.stub import StubCameraBackend
from core.camera.errors import (
    CameraDisabledError,
    CameraImageTooLargeError,
    CameraUnavailableError,
)
from core.camera.models import CameraStatus, CaptureResponse, FaceBox, RecognizeResponse
from core.config import CameraConfig, get_camera_config
from core.logging.audit import audit_event


class CameraService:
    def __init__(self, config: CameraConfig | None = None):
        self._config = config or get_camera_config()

    @property
    def config(self) -> CameraConfig:
        return self._config

    def status(self, request_id: str | None = None) -> CameraStatus:
        backend = self._get_backend()
        enabled = self._config.enabled
        available = enabled and backend.is_available()
        message = self._status_message(enabled=enabled, available=available, backend=backend)
        audit_event(
            "camera.status",
            request_id=request_id,
            backend=backend.name,
            enabled=enabled,
            available=available,
        )
        return CameraStatus(
            enabled=enabled,
            backend=backend.name,
            available=available,
            message=message,
        )

    def capture(self, request_id: str | None = None) -> CaptureResponse:
        backend = self._get_backend()
        if not self._config.enabled:
            audit_event(
                "camera.capture",
                request_id=request_id,
                backend=backend.name,
                enabled=False,
                result="disabled",
            )
            raise CameraDisabledError("Camera is disabled by configuration.")
        if not backend.is_available():
            audit_event(
                "camera.capture",
                request_id=request_id,
                backend=backend.name,
                enabled=True,
                result="unavailable",
            )
            raise CameraUnavailableError("Camera backend is unavailable.")
        frame = backend.capture_frame()
        if len(frame.data) > self._config.max_image_bytes:
            audit_event(
                "camera.capture",
                request_id=request_id,
                backend=backend.name,
                enabled=True,
                result="image_too_large",
                size=len(frame.data),
            )
            raise CameraImageTooLargeError("Captured image exceeds configured size limit.")
        image_b64 = base64.b64encode(frame.data).decode("utf-8")
        audit_event(
            "camera.capture",
            request_id=request_id,
            backend=backend.name,
            enabled=True,
            result="captured",
            width=frame.width,
            height=frame.height,
        )
        return CaptureResponse(
            captured=True,
            width=frame.width,
            height=frame.height,
            format=frame.format,
            image_base64=image_b64,
        )

    def recognize(self, request_id: str | None = None) -> RecognizeResponse:
        backend = self._get_backend()
        if not self._config.enabled:
            audit_event(
                "camera.recognize",
                request_id=request_id,
                backend=backend.name,
                enabled=False,
                result="disabled",
            )
            raise CameraDisabledError("Camera is disabled by configuration.")
        if not backend.is_available():
            audit_event(
                "camera.recognize",
                request_id=request_id,
                backend=backend.name,
                enabled=True,
                result="unavailable",
            )
            raise CameraUnavailableError("Camera backend is unavailable.")
        frame = backend.capture_frame()
        if len(frame.data) > self._config.max_image_bytes:
            audit_event(
                "camera.recognize",
                request_id=request_id,
                backend=backend.name,
                enabled=True,
                result="image_too_large",
                size=len(frame.data),
            )
            raise CameraImageTooLargeError("Captured image exceeds configured size limit.")
        boxes = backend.detect_faces(frame)
        audit_event(
            "camera.recognize",
            request_id=request_id,
            backend=backend.name,
            enabled=True,
            result="faces_detected",
            faces=len(boxes),
        )
        return RecognizeResponse(
            faces_detected=len(boxes),
            boxes=[FaceBox(x=box.x, y=box.y, w=box.w, h=box.h) for box in boxes],
            confidence=None,
        )

    def _status_message(self, *, enabled: bool, available: bool, backend: CameraBackend) -> str:
        if not enabled:
            return "Camera disabled by configuration."
        if not available:
            return f"Camera backend '{backend.name}' unavailable."
        if backend.name == "stub":
            return "Stub backend ready (no real camera)."
        return "Camera backend ready."

    def _get_backend(self) -> CameraBackend:
        if self._config.backend == "opencv":
            from core.camera.backends.opencv import OpenCVCameraBackend

            return OpenCVCameraBackend(self._config)
        return StubCameraBackend(self._config)
