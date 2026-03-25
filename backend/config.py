import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "database" / "attendance.db"
QR_DIR = BASE_DIR / "database" / "qr_codes"
MODELS_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "logs"

for directory in [QR_DIR, MODELS_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("ATTENDANCE_SECRET", "offline-hybrid-attendance-secret")
FACE_MIN_SIZE = (80, 80)
MOTION_THRESHOLD = 14.0
MOTION_COOLDOWN_SECONDS = 5
FRAME_RESIZE_WIDTH = 640
