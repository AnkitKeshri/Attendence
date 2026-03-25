import logging
import time
import uuid
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request, send_from_directory

from backend.config import LOG_DIR, MOTION_COOLDOWN_SECONDS, MOTION_THRESHOLD, SECRET_KEY
from backend.database import (
    create_student,
    fetch_attendance,
    get_student_by_qr,
    initialize_database,
    list_students,
    save_attendance,
)
from backend.vision import VisionEngine

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
app.config["SECRET_KEY"] = SECRET_KEY

vision = VisionEngine()
verification_cache: dict[str, dict] = {}


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "attendance.log"
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)


def _get_client_token() -> str:
    token = request.headers.get("X-Client-Token")
    if token:
        return token
    return str(uuid.uuid4())


def _get_or_create_state(token: str) -> dict:
    state = verification_cache.get(token)
    if not state:
        state = {
            "qr_verified": False,
            "qr_payload": None,
            "student": None,
            "face_detected": False,
            "motion_recent": False,
            "last_motion_time": 0.0,
            "previous_frame": None,
        }
        verification_cache[token] = state
    return state


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/qr_codes/<path:filename>")
def qr_codes(filename):
    return send_from_directory("../database/qr_codes", filename)


@app.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        payload = request.get_json(force=True, silent=True) or {}
        student_id = (payload.get("id") or "").strip()
        name = (payload.get("name") or "").strip()

        if not student_id or not name:
            return jsonify({"ok": False, "message": "Both id and name are required"}), 400
        try:
            create_student(student_id=student_id, name=name)
            app.logger.info("Student created: %s - %s", student_id, name)
            return jsonify({"ok": True, "message": "Student created", "student_id": student_id})
        except Exception as exc:  # sqlite uniqueness and file errors
            app.logger.warning("Student creation failed: %s", exc)
            return jsonify({"ok": False, "message": str(exc)}), 400

    students_data = list_students()
    return jsonify({"ok": True, "students": students_data})


@app.route("/scan_qr", methods=["POST"])
def scan_qr():
    token = _get_client_token()
    state = _get_or_create_state(token)

    payload = request.get_json(force=True, silent=True) or {}
    image_b64 = payload.get("image")
    if not image_b64:
        return jsonify({"ok": False, "message": "Image is required", "token": token}), 400

    try:
        frame = vision.decode_base64_image(image_b64)
        qr_result = vision.detect_qr(frame)
    except Exception as exc:
        app.logger.warning("QR scan error: %s", exc)
        return jsonify({"ok": False, "message": "Unable to process QR frame", "token": token}), 400

    if not qr_result.found:
        return jsonify({"ok": False, "message": "No valid QR found", "token": token})

    student = get_student_by_qr(qr_result.details["qr_data"])
    if not student:
        return jsonify({"ok": False, "message": "QR not registered", "token": token})

    state["qr_verified"] = True
    state["qr_payload"] = qr_result.details["qr_data"]
    state["student"] = {"id": student["id"], "name": student["name"]}

    app.logger.info("QR verified for student=%s token=%s", student["id"], token)
    return jsonify(
        {
            "ok": True,
            "message": "QR Verified",
            "token": token,
            "student": state["student"],
        }
    )


@app.route("/detect_face", methods=["POST"])
def detect_face():
    token = _get_client_token()
    state = _get_or_create_state(token)

    payload = request.get_json(force=True, silent=True) or {}
    image_b64 = payload.get("image")
    if not image_b64:
        return jsonify({"ok": False, "message": "Image is required", "token": token}), 400

    try:
        frame = vision.decode_base64_image(image_b64)
        face_result = vision.detect_face(frame)
        motion_score = vision.compute_motion_score(frame, state["previous_frame"])
        state["previous_frame"] = frame
    except Exception as exc:
        app.logger.warning("Face detection error: %s", exc)
        return jsonify({"ok": False, "message": "Unable to process face frame", "token": token}), 400

    now = time.time()
    if motion_score >= MOTION_THRESHOLD:
        state["last_motion_time"] = now

    state["motion_recent"] = now - state["last_motion_time"] <= MOTION_COOLDOWN_SECONDS
    state["face_detected"] = face_result.found

    message = "Face Detected" if face_result.found else "No face detected"
    if face_result.found and not state["motion_recent"]:
        message = "Face found, but anti-spoof motion check failed"

    return jsonify(
        {
            "ok": True,
            "message": message,
            "token": token,
            "face_detected": face_result.found,
            "motion_score": round(motion_score, 2),
            "motion_recent": state["motion_recent"],
            "faces": face_result.details["faces"],
        }
    )


@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    token = _get_client_token()
    state = _get_or_create_state(token)

    if not state["qr_verified"]:
        return jsonify({"ok": False, "message": "QR verification required", "token": token}), 400
    if not state["face_detected"]:
        return jsonify({"ok": False, "message": "Face detection required", "token": token}), 400
    if not state["motion_recent"]:
        return jsonify({"ok": False, "message": "Anti-spoof motion check failed", "token": token}), 400

    success, message = save_attendance(student_id=state["student"]["id"])
    status_code = 200 if success else 409
    app.logger.info(
        "Mark attendance token=%s student=%s success=%s",
        token,
        state["student"]["id"],
        success,
    )

    if success:
        state["qr_verified"] = False
        state["face_detected"] = False
        state["motion_recent"] = False

    return jsonify(
        {
            "ok": success,
            "message": "Attendance Marked" if success else message,
            "details": message,
            "student": state["student"],
            "token": token,
        }
    ), status_code


@app.route("/get_attendance", methods=["GET"])
def get_attendance():
    date_filter = request.args.get("date")
    rows = fetch_attendance(date_filter=date_filter)
    return jsonify({"ok": True, "attendance": rows, "count": len(rows)})


if __name__ == "__main__":
    initialize_database()
    configure_logging()
    app.run(host="0.0.0.0", port=5000, debug=False)
