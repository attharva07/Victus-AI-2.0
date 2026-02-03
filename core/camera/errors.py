from __future__ import annotations


class CameraError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class CameraDisabledError(CameraError):
    def __init__(self, message: str = "Camera is disabled."):
        super().__init__(message, status_code=403)


class CameraUnavailableError(CameraError):
    def __init__(self, message: str = "Camera backend unavailable."):
        super().__init__(message, status_code=503)


class CameraImageTooLargeError(CameraError):
    def __init__(self, message: str = "Captured image exceeds size limit."):
        super().__init__(message, status_code=413)
