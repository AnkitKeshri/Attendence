import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "attendance.db"

st.set_page_config(page_title="Attendance Dashboard", layout="wide")
st.title("Offline Hybrid Attendance Dashboard")


@st.cache_data
def load_data():
    if not DB_PATH.exists():
        return pd.DataFrame(), pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    students = pd.read_sql_query("SELECT id, name FROM students", conn)
    attendance = pd.read_sql_query("SELECT student_id, date, time, status FROM attendance", conn)
    conn.close()
    return students, attendance


students_df, attendance_df = load_data()

if students_df.empty:
    st.warning("No students found. Register students from Flask app first.")
    st.stop()

if attendance_df.empty:
    st.info("No attendance records yet.")
    st.dataframe(students_df)
    st.stop()

attendance_df["date"] = pd.to_datetime(attendance_df["date"])
dates = sorted(attendance_df["date"].dt.date.unique(), reverse=True)
selected_date = st.selectbox("Select date", options=dates, index=0)

filtered = attendance_df[attendance_df["date"].dt.date == selected_date]
merged = filtered.merge(students_df, left_on="student_id", right_on="id", how="left")

st.subheader(f"Daily Report - {selected_date}")
st.dataframe(merged[["student_id", "name", "date", "time", "status"]], use_container_width=True)

present_counts = attendance_df.groupby("student_id").size().reset_index(name="days_present")
summary = students_df.merge(present_counts, left_on="id", right_on="student_id", how="left")
summary["days_present"] = summary["days_present"].fillna(0)

total_days = max(attendance_df["date"].nunique(), 1)
summary["attendance_percentage"] = (summary["days_present"] / total_days * 100).round(2)

st.subheader("Student-wise Attendance %")
st.dataframe(summary[["id", "name", "days_present", "attendance_percentage"]], use_container_width=True)
st.bar_chart(summary.set_index("name")["attendance_percentage"])

csv = summary[["id", "name", "days_present", "attendance_percentage"]].to_csv(index=False).encode("utf-8")
st.download_button(
    label="Export Attendance CSV",
    data=csv,
    file_name="attendance_summary.csv",
    mime="text/csv",
)
