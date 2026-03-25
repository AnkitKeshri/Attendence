# Offline Hybrid Attendance System (QR + Face Detection)

A complete offline attendance system that marks attendance only when **both** conditions are true:
1. Valid student QR is detected.
2. Live human face is detected with basic anti-spoof motion check.

## Project Structure

```
Attendence/
├── backend/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── database.py
│   ├── run.py
│   └── vision.py
├── dashboard/
│   └── app.py
├── database/
│   ├── attendance.db          # auto-created at runtime
│   └── qr_codes/              # auto-generated student QR images
├── frontend/
│   ├── static/
│   │   ├── css/styles.css
│   │   └── js/app.js
│   └── templates/index.html
├── logs/
│   └── attendance.log         # auto-created at runtime
├── models/
│   └── README.md
├── requirements.txt
└── README.md
```

## Core Features Implemented

- Offline QR verification from live WebRTC camera frames.
- Offline face detection with Haar Cascade (no biometric storage).
- Dual verification logic: attendance saved only when QR + face + motion check pass.
- Anti-spoofing (basic): frame-to-frame motion score must exceed threshold recently.
- SQLite schema:
  - `students(id, name, qr_code, qr_image_path, created_at)`
  - `attendance(id, student_id, date, time, status, method)`
- Flask APIs:
  - `POST /scan_qr`
  - `POST /detect_face`
  - `POST /mark_attendance`
  - `GET /get_attendance`
  - `GET/POST /students`
- Streamlit dashboard with daily report, attendance %, chart, CSV export.
- Logging with rotating file handler.
- Graceful handling for invalid QR, no face, spoof failure, and camera issues.

## Setup Instructions

### 1) Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run Flask backend + frontend

```bash
python -m backend.run
```

Open in browser:

- `http://127.0.0.1:5000`

### 4) Run Streamlit dashboard

In a new terminal (same venv):

```bash
streamlit run dashboard/app.py
```

Open dashboard URL shown in terminal (typically `http://localhost:8501`).

## How to Use Locally

1. Open Flask UI.
2. Register students with ID and name.
   - QR images are generated in `database/qr_codes/`.
3. Click **Start Camera**.
4. Show QR in camera and keep person in frame.
5. Ensure status shows:
   - `QR: Verified`
   - `Face: Detected + Live`
6. Click **Mark Attendance**.
7. Review records in table and dashboard.

## Performance + Robustness Notes

- Frames are JPEG-compressed in browser before sending to reduce CPU/network overhead.
- Detection uses resized frames for low-end devices.
- Low-light enhancement via CLAHE preprocessing before detection.
- Attendance deduplication enforced per student per day.
- No internet or cloud API is required.

## Security/Privacy Notes

- No facial recognition or biometric template storage.
- Face checks only verify presence and liveness-like motion.
- Entire system runs offline on local machine/LAN.
