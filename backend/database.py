import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import qrcode

from backend.config import DATABASE_PATH, QR_DIR


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_cursor(commit: bool = False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    finally:
        cur.close()
        conn.close()


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                qr_code TEXT NOT NULL UNIQUE,
                qr_image_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL,
                method TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            """
        )


def generate_qr_payload(student_id: str, name: str) -> str:
    return f"{student_id}|{name}"


def create_student(student_id: str, name: str):
    qr_payload = generate_qr_payload(student_id=student_id, name=name)
    qr_image_path = QR_DIR / f"{student_id}.png"
    qr_img = qrcode.make(qr_payload)
    qr_img.save(qr_image_path)

    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO students(id, name, qr_code, qr_image_path, created_at)
            VALUES(?,?,?,?,?)
            """,
            (student_id, name, qr_payload, str(qr_image_path), datetime.utcnow().isoformat()),
        )


def get_student_by_qr(qr_payload: str):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM students WHERE qr_code = ?", (qr_payload,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_student(student_id: str):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def save_attendance(student_id: str, status: str = "Present", method: str = "qr+face"):
    now = datetime.now()
    date_value = now.strftime("%Y-%m-%d")
    time_value = now.strftime("%H:%M:%S")

    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            SELECT id FROM attendance
            WHERE student_id = ? AND date = ?
            """,
            (student_id, date_value),
        )
        existing = cur.fetchone()
        if existing:
            return False, "Attendance already marked for today"

        cur.execute(
            """
            INSERT INTO attendance(student_id, date, time, status, method)
            VALUES(?,?,?,?,?)
            """,
            (student_id, date_value, time_value, status, method),
        )
    return True, "Attendance marked successfully"


def fetch_attendance(date_filter: str | None = None):
    query = (
        """
        SELECT a.id, a.student_id, s.name, a.date, a.time, a.status, a.method
        FROM attendance a
        INNER JOIN students s ON s.id = a.student_id
        """
    )
    params = []
    if date_filter:
        query += " WHERE a.date = ?"
        params.append(date_filter)
    query += " ORDER BY a.date DESC, a.time DESC"

    with db_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(row) for row in rows]


def list_students():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, qr_code, qr_image_path FROM students ORDER BY id")
        rows = cur.fetchall()
    return [dict(row) for row in rows]
