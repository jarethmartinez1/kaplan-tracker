"""Parse Kaplan Excel export into structured data for the database."""
import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd


EXCEL_COLUMNS = [
    "Reporting Location", "Customer ID", "Order ID", "First Name", "Last Name",
    "Email", "Course Group", "Course Subject", "Course Name", "Course Status",
    "Credit Type/Field Of Study", "Credit Hours", "Regulator Course ID",
    "Credit State", "Delivery Type", "Score", "Seat Time",
    "Status Last Updated Date", "Enrollment Date", "Completion Date",
    "Access Expiration Date", "First Access Date", "Last Access Date",
    "Last Activity Completed", "Last Activity Completed Date",
    "Phone", "Employe ID", "Address Line 1", "Address Line 2",
    "City", "State", "Postal Code", "Country",
]


def parse_kaplan_excel(file_path: str | Path) -> pd.DataFrame:
    """Parse a Kaplan enrollment report Excel export.

    Handles the header rows (title, timezone, blank, column headers)
    and returns a clean DataFrame with proper column names and types.
    """
    df = pd.read_excel(file_path, header=None, skiprows=4)
    df.columns = EXCEL_COLUMNS

    # Clean up types
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce")
    df["Credit Hours"] = pd.to_numeric(df["Credit Hours"], errors="coerce")
    df["Customer ID"] = df["Customer ID"].astype(str)

    # Parse dates
    date_cols = [
        "Enrollment Date", "Completion Date", "Access Expiration Date",
        "First Access Date", "Last Access Date", "Status Last Updated Date",
        "Last Activity Completed Date",
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Parse seat time (HH:MM:SS) into minutes
    df["Seat Time Minutes"] = df["Seat Time"].apply(_parse_seat_time)

    # Full name
    df["Name"] = (df["First Name"].fillna("") + " " + df["Last Name"].fillna("")).str.strip()

    # External ID from customer ID
    df["External ID"] = df["Customer ID"]

    return df


def _parse_seat_time(val) -> int | None:
    """Parse seat time like '40:41:35' into total minutes."""
    if pd.isna(val) or not val:
        return None
    try:
        parts = str(val).split(":")
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 60 + m + (1 if s >= 30 else 0)
        elif len(parts) == 2:
            h, m = int(parts[0]), int(parts[1])
            return h * 60 + m
    except (ValueError, IndexError):
        pass
    return None


def aggregate_per_candidate(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate course-level data to per-candidate summary."""
    grouped = df.groupby(["External ID", "Name", "Email"]).agg(
        total_courses=("Course Name", "count"),
        completed_courses=("Course Status", lambda x: (x == "Completed").sum()),
        avg_score=("Score", "mean"),
        min_score=("Score", "min"),
        max_score=("Score", "max"),
        total_seat_minutes=("Seat Time Minutes", "sum"),
        earliest_enrollment=("Enrollment Date", "min"),
        latest_completion=("Completion Date", "max"),
        latest_access=("Last Access Date", "max"),
        courses_list=("Course Name", list),
    ).reset_index()

    grouped["completion_pct"] = (
        grouped["completed_courses"] / grouped["total_courses"] * 100
    ).round(1)

    return grouped
