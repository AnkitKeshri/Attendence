import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.config import FACE_MIN_SIZE, FRAME_RESIZE_WIDTH, MODELS_DIR


@dataclass
class DetectionResult:
    found: bool
    details: dict


class VisionEngine:
    def __init__(self):
        self.face_cascade = self._load_cascade("haarcascade_frontalface_default.xml")
        self.eye_cascade = self._load_cascade("haarcascade_eye.xml")
        self.qr_detector = cv2.QRCodeDetector()

    def _load_cascade(self, cascade_name: str) -> cv2.CascadeClassifier:
        local_path = MODELS_DIR / cascade_name
        if not local_path.exists():
            cv_path = Path(cv2.data.haarcascades) / cascade_name
            if cv_path.exists():
                local_path.write_bytes(cv_path.read_bytes())
            else:
                raise FileNotFoundError(f"Cascade file missing: {cascade_name}")

        cascade = cv2.CascadeClassifier(str(local_path))
        if cascade.empty():
            raise RuntimeError(f"Failed to load cascade classifier: {cascade_name}")
        return cascade

    @staticmethod
    def decode_base64_image(image_b64: str) -> np.ndarray:
        raw = image_b64.split(",")[-1]
        binary = base64.b64decode(raw)
        array = np.frombuffer(binary, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Invalid image payload")
        return frame

    @staticmethod
    def optimize_frame(frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        if width <= FRAME_RESIZE_WIDTH:
            return frame
        ratio = FRAME_RESIZE_WIDTH / width
        return cv2.resize(frame, (int(width * ratio), int(height * ratio)), interpolation=cv2.INTER_AREA)

    @staticmethod
    def enhance_low_light(frame: np.ndarray) -> np.ndarray:
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        y = clahe.apply(y)
        merged = cv2.merge((y, cr, cb))
        return cv2.cvtColor(merged, cv2.COLOR_YCrCb2BGR)

    def detect_qr(self, frame: np.ndarray) -> DetectionResult:
        value, points, _ = self.qr_detector.detectAndDecode(frame)
        if value:
            return DetectionResult(True, {"qr_data": value.strip(), "points": points.tolist() if points is not None else []})
        return DetectionResult(False, {"qr_data": None, "points": []})

    def detect_face(self, frame: np.ndarray) -> DetectionResult:
        frame = self.optimize_frame(frame)
        frame = self.enhance_low_light(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=FACE_MIN_SIZE,
        )

        face_boxes = []
        eye_count = 0
        for x, y, w, h in faces:
            roi_gray = gray[y : y + h, x : x + w]
            eyes = self.eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.15, minNeighbors=3, minSize=(18, 18))
            eye_count += len(eyes)
            face_boxes.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h), "eyes": int(len(eyes))})

        found = len(faces) > 0
        return DetectionResult(found, {"faces": face_boxes, "eye_count": eye_count, "frame_shape": frame.shape[:2]})

    @staticmethod
    def compute_motion_score(current_frame: np.ndarray, previous_frame: Optional[np.ndarray]) -> float:
        if previous_frame is None:
            return 0.0
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
        current_gray = cv2.GaussianBlur(current_gray, (5, 5), 0)
        previous_gray = cv2.GaussianBlur(previous_gray, (5, 5), 0)
        delta = cv2.absdiff(current_gray, previous_gray)
        return float(np.mean(delta))
