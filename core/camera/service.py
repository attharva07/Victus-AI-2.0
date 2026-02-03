from __future__ import annotations

from core.camera.backends.base import CameraBackend
from core.camera.backends.stub import StubCameraBackend
from core.camera.models import CameraStatus, CaptureResponse, RecognizeResponse
from core.config import CameraConfig, get_camera_config
from core.logging.audit import audit_event


class CameraService:
    def __init__(self, config: CameraConfig | None = None):
        self._config = config or get_camera_config()

    @property
    def config(self) -> CameraConfig:
        return self._config

    def status(self, request_id: str | None = None) -> CameraStatus:
        enabled = self._config.enabled
        backend_name = self._config.backend
        available = False
        message = self._status_message(enabled=enabled, backend_name=backend_name)
        if enabled:
            backend = self._get_backend()
            available = backend.is_available()
            if available:
                message = self._status_message(
                    enabled=enabled, backend_name=backend.name, available=available
                )
        audit_event(
            "camera.status",
            action="status",
            request_id=request_id,
            backend=backend_name,
            enabled=enabled,
        )
        return CameraStatus(
            enabled=enabled,
            backend=backend_name,
            ok=enabled and available,
            message=message,
        )

    def capture(
        self,
        request_id: str | None = None,
        *,
        reason: str | None = None,
        format: str = "jpg",
    ) -> CaptureResponse:
        if not self._config.enabled:
            audit_event(
                "camera.capture",
                action="capture",
                request_id=request_id,
                backend=self._config.backend,
                enabled=False,
            )
            return CaptureResponse(
                ok=False,
                enabled=False,
                backend=self._config.backend,
                capture_id=None,
                stored=False,
                message="Camera is disabled by configuration.",
            )
        backend = self._get_backend()
        if not backend.is_available():
            audit_event(
                "camera.capture",
                action="capture",
                request_id=request_id,
                backend=backend.name,
                enabled=True,
                result="unavailable",
            )
            return CaptureResponse(
                ok=False,
                enabled=True,
                backend=backend.name,
                capture_id=None,
                stored=False,
                message="Camera backend is unavailable.",
            )
        capture_id = request_id or "stub-capture"
        audit_event(
            "camera.capture",
            action="capture",
            request_id=request_id,
            backend=backend.name,
            enabled=True,
            result="stubbed",
            reason=reason,
            format=format,
        )
        return CaptureResponse(
            ok=True,
            enabled=True,
            backend=backend.name,
            capture_id=capture_id,
            stored=False,
            message="Stub capture recorded (no image stored).",
        )

    def recognize(
        self,
        request_id: str | None = None,
        *,
        capture_id: str | None = None,
        image_b64: str | None = None,
    ) -> RecognizeResponse:
        if not self._config.enabled:
            audit_event(
                "camera.recognize",
                action="recognize",
                request_id=request_id,
                backend=self._config.backend,
                enabled=False,
            )
            return RecognizeResponse(
                ok=False,
                enabled=False,
                backend=self._config.backend,
                matches=[],
                message="Camera is disabled by configuration.",
            )
        backend = self._get_backend()
        if not backend.is_available():
            audit_event(
                "camera.recognize",
                action="recognize",
                request_id=request_id,
                backend=backend.name,
                enabled=True,
                result="unavailable",
            )
            return RecognizeResponse(
                ok=False,
                enabled=True,
                backend=backend.name,
                matches=[],
                message="Camera backend is unavailable.",
            )
        audit_event(
            "camera.recognize",
            action="recognize",
            request_id=request_id,
            backend=backend.name,
            enabled=True,
            result="stubbed",
            capture_id=capture_id,
            image_b64_provided=image_b64 is not None,
        )
        return RecognizeResponse(
            ok=True,
            enabled=True,
            backend=backend.name,
            matches=[],
            message="Stub recognition complete (no matches).",
        )

    def _status_message(
        self, *, enabled: bool, backend_name: str, available: bool = False
    ) -> str:
        if not enabled:
            return "Camera disabled by configuration."
        if not available:
            return f"Camera backend '{backend_name}' unavailable."
        if backend_name == "stub":
            return "Stub backend ready (no real camera)."
        return "Camera backend ready."

    def _get_backend(self) -> CameraBackend:
        if self._config.backend == "opencv":
            from core.camera.backends.opencv import OpenCVCameraBackend

            return OpenCVCameraBackend(self._config)
        return StubCameraBackend(self._config)
