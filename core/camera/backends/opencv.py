from __future__ import annotations

import importlib
import importlib.util

from core.camera.backends.base import CameraBackend, CameraFrame, FaceBox
from core.camera.errors import CameraUnavailableError
from core.config import CameraConfig


def _cv2_available() -> bool:
    return importlib.util.find_spec("cv2") is not None


class OpenCVCameraBackend(CameraBackend):
    name = "opencv"

    def __init__(self, config: CameraConfig):
        self._config = config

    def is_available(self) -> bool:
        if not _cv2_available():
            return False
        cv2 = importlib.import_module("cv2")
        capture = cv2.VideoCapture(self._config.device_index)
        if not capture or not capture.isOpened():
            return False
        capture.release()
        return True

    def capture_frame(self) -> CameraFrame:
        if not _cv2_available():
            raise CameraUnavailableError("OpenCV is not installed.")
        cv2 = importlib.import_module("cv2")
        capture = cv2.VideoCapture(self._config.device_index)
        if not capture or not capture.isOpened():
            raise CameraUnavailableError("Camera device not available.")
        success, frame = capture.read()
        capture.release()
        if not success or frame is None:
            raise CameraUnavailableError("Failed to capture frame.")
        frame = self._resize_to_max(frame, self._config.max_dim, cv2)
        height, width = frame.shape[:2]
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            raise CameraUnavailableError("Failed to encode frame.")
        return CameraFrame(data=buffer.tobytes(), width=width, height=height, format="jpeg")

    def detect_faces(self, frame: CameraFrame) -> list[FaceBox]:
        if not _cv2_available():
            raise CameraUnavailableError("OpenCV is not installed.")
        cv2 = importlib.import_module("cv2")
        numpy = importlib.import_module("numpy")
        buffer = numpy.frombuffer(frame.data, dtype=numpy.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise CameraUnavailableError("Failed to decode frame.")
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        if detector.empty():
            return []
        faces = detector.detectMultiScale(image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        return [FaceBox(x=int(x), y=int(y), w=int(w), h=int(h)) for x, y, w, h in faces]

    @staticmethod
    def _resize_to_max(frame, max_dim: int, cv2_module):
        height, width = frame.shape[:2]
        longest = max(height, width)
        if longest <= max_dim:
            return frame
        scale = max_dim / float(longest)
        new_width = int(width * scale)
        new_height = int(height * scale)
        return cv2_module.resize(frame, (new_width, new_height))
