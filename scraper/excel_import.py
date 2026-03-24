"""
Import candidate data from Kaplan Excel export.

Usage:
    python scripts/run_import.py path/to/export.xlsx

This replaces DOM scraping — just export from Kaplan's Enrollment Report
and feed the Excel file to this importer.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.database import get_session, init_db
from data.models import (
    Candidate,
    LessonProgress,
    ProgressSnapshot,
    QuizScore,
    StudySession,
)

# Column names in the Kaplan export (header row is row index 3, data starts row 4)
EXPORT_COLUMNS = [
    "Reporting Location", "Customer ID", "Order ID", "First Name", "Last Name",
    "Email", "Course Group", "Course Subject", "Course Name", "Course Status",
    "Credit Type", "Credit Hours", "Regulator Course ID", "Credit State",
    "Delivery Type", "Score", "Seat Time", "Status Last Updated",
    "Enrollment Date", "Completion Date", "Access Expiration Date",
    "First Access Date", "Last Access Date", "Last Activity Completed",
    "Last Activity Completed Date", "Phone", "Employee ID",
    "Address Line 1", "Address Line 2", "City", "State", "Postal Code", "Country",
]


def parse_seat_time(seat_time_str: str | None) -> int:
    """Parse seat time like '40:41:35' (H:MM:SS) into total minutes."""
    if not seat_time_str or pd.isna(seat_time_str):
        return 0
    parts = str(seat_time_str).split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        else:
            return int(float(parts[0]) * 60)
    except (ValueError, IndexError):
        return 0


def load_excel(filepath: str) -> pd.DataFrame:
    """Load and clean the Kaplan Excel export."""
    df = pd.read_excel(filepath, header=None, skiprows=4)

    # Handle case where export has fewer columns than expected
    if len(df.columns) <= len(EXPORT_COLUMNS):
        df.columns = EXPORT_COLUMNS[: len(df.columns)]
    else:
        df = df.iloc[:, : len(EXPORT_COLUMNS)]
        df.columns = EXPORT_COLUMNS

    # Drop fully empty rows
    df = df.dropna(how="all")

    # Parse dates
    for col in ["Enrollment Date", "Completion Date", "First Access Date", "Last Access Date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Parse score as numeric
    if "Score" in df.columns:
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce")

    return df


def import_to_db(df: pd.DataFrame):
    """Import parsed Excel data into the SQLite database."""
    engine = init_db()
    session = get_session(engine)

    # Group by candidate (Email is unique identifier)
    grouped = df.groupby("Email")

    imported = 0
    for email, candidate_courses in grouped:
        if pd.isna(email):
            continue

        first_row = candidate_courses.iloc[0]
        name = f"{first_row['First Name']} {first_row['Last Name']}".strip()
        customer_id = str(first_row.get("Customer ID", ""))

        # Earliest enrollment date across all courses
        enrollment_date = candidate_courses["Enrollment Date"].min()
        if pd.notna(enrollment_date):
            enrollment_date = enrollment_date.date()
        else:
            enrollment_date = None

        # First/last access dates across all courses
        first_access = candidate_courses["First Access Date"].min()
        first_access_date = first_access.date() if pd.notna(first_access) else None
        last_access = candidate_courses["Last Access Date"].max()
        last_access_date = last_access.date() if pd.notna(last_access) else None

        total_courses = len(candidate_courses)
        completed_courses = len(
            candidate_courses[candidate_courses["Course Status"] == "Completed"]
        )

        # Upsert candidate
        candidate = session.query(Candidate).filter_by(external_id=customer_id).first()
        if candidate:
            candidate.name = name
            candidate.email = email
            candidate.enrollment_date = enrollment_date
            candidate.first_access_date = first_access_date
            candidate.last_access_date = last_access_date
            candidate.total_lessons = total_courses
        else:
            candidate = Candidate(
                external_id=customer_id,
                name=name,
                email=email,
                enrollment_date=enrollment_date,
                first_access_date=first_access_date,
                last_access_date=last_access_date,
                total_lessons=total_courses,
            )
            session.add(candidate)
        session.flush()

        # Store each course as a "lesson"
        today = date.today()
        total_seat_minutes = 0
        scores = []

        for _, course in candidate_courses.iterrows():
            course_name = course.get("Course Name", "Unknown")
            status = course.get("Course Status", "")
            normalized_status = "completed" if status == "Completed" else "in_progress"

            completion_date = course.get("Completion Date")
            if pd.notna(completion_date):
                completion_date = completion_date.date()
            else:
                completion_date = None

            # Lesson progress
            existing_lesson = (
                session.query(LessonProgress)
                .filter_by(
                    candidate_id=candidate.id,
                    lesson_name=course_name,
                    scraped_at=today,
                )
                .first()
            )
            if not existing_lesson:
                session.add(
                    LessonProgress(
                        candidate_id=candidate.id,
                        lesson_name=course_name,
                        status=normalized_status,
                        date_completed=completion_date,
                        scraped_at=today,
                    )
                )

            # Quiz score (the final exam score for each course)
            score = course.get("Score")
            if pd.notna(score):
                scores.append(float(score))
                exam_date = completion_date or today
                existing_quiz = (
                    session.query(QuizScore)
                    .filter_by(
                        candidate_id=candidate.id,
                        quiz_name=course_name,
                        date_taken=exam_date,
                    )
                    .first()
                )
                if not existing_quiz:
                    session.add(
                        QuizScore(
                            candidate_id=candidate.id,
                            quiz_name=course_name,
                            score=float(score),
                            passing_score=70.0,  # Standard Kaplan RE passing score
                            passed=float(score) >= 70.0,
                            date_taken=exam_date,
                            scraped_at=today,
                        )
                    )

            # Seat time as study session
            seat_minutes = parse_seat_time(course.get("Seat Time"))
            total_seat_minutes += seat_minutes
            if seat_minutes > 0:
                first_access = course.get("First Access Date")
                session_date = first_access.date() if pd.notna(first_access) else today
                existing_session = (
                    session.query(StudySession)
                    .filter_by(
                        candidate_id=candidate.id,
                        session_date=session_date,
                    )
                    .first()
                )
                if not existing_session:
                    session.add(
                        StudySession(
                            candidate_id=candidate.id,
                            session_date=session_date,
                            duration_minutes=seat_minutes,
                            scraped_at=today,
                        )
                    )

        # Progress snapshot
        completion_pct = (completed_courses / total_courses * 100) if total_courses > 0 else 0
        avg_score = sum(scores) / len(scores) if scores else None

        existing_snapshot = (
            session.query(ProgressSnapshot)
            .filter_by(candidate_id=candidate.id, snapshot_date=today)
            .first()
        )
        snapshot_data = {
            "lessons_completed": completed_courses,
            "total_lessons": total_courses,
            "completion_pct": round(completion_pct, 1),
            "total_study_minutes": total_seat_minutes,
            "avg_quiz_score": round(avg_score, 1) if avg_score else None,
            "quizzes_passed": len([s for s in scores if s >= 70]),
            "quizzes_total": len(scores),
        }
        if existing_snapshot:
            for k, v in snapshot_data.items():
                setattr(existing_snapshot, k, v)
        else:
            session.add(
                ProgressSnapshot(
                    candidate_id=candidate.id,
                    snapshot_date=today,
                    **snapshot_data,
                )
            )

        imported += 1

    session.commit()
    session.close()
    return imported


def main(filepath: str):
    print(f"Loading Excel export: {filepath}")
    df = load_excel(filepath)
    print(f"  Found {len(df)} rows, {df['Email'].dropna().nunique()} unique candidates")

    # Clear old demo data
    engine = init_db()
    session = get_session(engine)
    session.query(ProgressSnapshot).delete()
    session.query(QuizScore).delete()
    session.query(StudySession).delete()
    session.query(LessonProgress).delete()
    session.query(Candidate).delete()
    session.commit()
    session.close()
    print("  Cleared old data.")

    count = import_to_db(df)
    print(f"  Imported {count} candidates.")
    print("Done! Launch the dashboard with: streamlit run dashboard/app.py")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraper/excel_import.py <path-to-export.xlsx>")
        sys.exit(1)
    main(sys.argv[1])
