from datetime import date, timedelta

import pandas as pd


INACTIVE_THRESHOLD_DAYS = 90
OVERDUE_INACTIVE_DAYS = 120
TARGET_WEEKS_FROM_START = 4
BEHIND_HRS_PER_WEEK = 20


def avg_hours_per_week(
    first_access_date: date | None,
    last_access_date: date | None,
    total_study_minutes: int | None,
) -> float | None:
    """
    Average study hours per week based on total study time
    spread over the active window (first_access → last_access).
    Returns None if calculation is not possible.
    """
    if not first_access_date or not last_access_date:
        return None
    if not total_study_minutes or total_study_minutes <= 0:
        return None

    days_active = (last_access_date - first_access_date).days
    if days_active <= 0:
        # Only one day of access — treat as 1 week
        weeks = 1.0
    else:
        weeks = max(days_active / 7.0, 1.0)

    return (total_study_minutes / 60.0) / weeks


def classify_risk(
    completion_pct: float,
    hrs_per_week: float | None,
    last_access_date: date | None,
    target_date: date | None = None,
) -> str:
    """Classify candidate status based on avg hours per week."""
    if completion_pct >= 100:
        return "complete"

    if completion_pct == 0:
        return "not_started"

    # Check inactivity
    days_since_access = (date.today() - last_access_date).days if last_access_date else None
    inactive = days_since_access is not None and days_since_access > INACTIVE_THRESHOLD_DAYS

    if inactive:
        return "inactive"

    if hrs_per_week is None:
        return "unknown"

    past_target = target_date and date.today() > target_date

    if hrs_per_week >= BEHIND_HRS_PER_WEEK:
        if not past_target:
            return "on_pace"
        return "at_risk"
    else:
        return "behind"


def load_candidates_df(session) -> pd.DataFrame:
    """Load candidates with latest snapshot data."""
    from data.models import Candidate, ProgressSnapshot

    query = (
        session.query(
            Candidate.id,
            Candidate.name,
            Candidate.email,
            Candidate.enrollment_date,
            Candidate.first_access_date,
            Candidate.last_access_date,
            Candidate.total_lessons,
            ProgressSnapshot.lessons_completed,
            ProgressSnapshot.completion_pct,
            ProgressSnapshot.total_study_minutes,
            ProgressSnapshot.avg_quiz_score,
            ProgressSnapshot.quizzes_passed,
            ProgressSnapshot.quizzes_total,
            ProgressSnapshot.snapshot_date,
        )
        .outerjoin(ProgressSnapshot, Candidate.id == ProgressSnapshot.candidate_id)
        .order_by(ProgressSnapshot.snapshot_date.desc())
    )

    rows = query.all()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        "id", "name", "email", "enrollment_date", "first_access_date",
        "last_access_date", "total_lessons",
        "lessons_completed", "completion_pct", "total_study_minutes",
        "avg_quiz_score", "quizzes_passed", "quizzes_total", "snapshot_date",
    ])

    # Keep only latest snapshot per candidate
    df = df.drop_duplicates(subset=["id"], keep="first")

    # Compute avg hours per week
    df["avg_hrs_per_week"] = df.apply(
        lambda r: avg_hours_per_week(
            r["first_access_date"], r["last_access_date"],
            r["total_study_minutes"] or 0,
        ),
        axis=1,
    )

    # Compute target date: first_access + 4 weeks
    df["target_date"] = df["first_access_date"].apply(
        lambda d: d + timedelta(weeks=TARGET_WEEKS_FROM_START) if pd.notna(d) else None
    )

    # Add risk classification
    df["risk_status"] = df.apply(
        lambda r: classify_risk(
            r["completion_pct"] or 0, r["avg_hrs_per_week"],
            r["last_access_date"], r["target_date"],
        ),
        axis=1,
    )

    return df


def load_quizzes_df(session) -> pd.DataFrame:
    from data.models import Candidate, QuizScore

    query = (
        session.query(
            Candidate.name.label("candidate_name"),
            QuizScore.quiz_name,
            QuizScore.score,
            QuizScore.passing_score,
            QuizScore.passed,
            QuizScore.date_taken,
        )
        .join(Candidate, QuizScore.candidate_id == Candidate.id)
        .order_by(QuizScore.date_taken)
    )

    rows = query.all()
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=[
        "candidate_name", "quiz_name", "score", "passing_score", "passed", "date_taken",
    ])


def load_study_sessions_df(session) -> pd.DataFrame:
    from data.models import Candidate, StudySession

    query = (
        session.query(
            Candidate.name.label("candidate_name"),
            StudySession.session_date,
            StudySession.duration_minutes,
        )
        .join(Candidate, StudySession.candidate_id == Candidate.id)
        .order_by(StudySession.session_date)
    )

    rows = query.all()
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=[
        "candidate_name", "session_date", "duration_minutes",
    ])


def load_snapshots_df(session) -> pd.DataFrame:
    from data.models import Candidate, ProgressSnapshot

    query = (
        session.query(
            Candidate.name.label("candidate_name"),
            ProgressSnapshot.snapshot_date,
            ProgressSnapshot.completion_pct,
            ProgressSnapshot.avg_quiz_score,
            ProgressSnapshot.total_study_minutes,
        )
        .join(Candidate, ProgressSnapshot.candidate_id == Candidate.id)
        .order_by(ProgressSnapshot.snapshot_date)
    )

    rows = query.all()
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=[
        "candidate_name", "snapshot_date", "completion_pct", "avg_quiz_score", "total_study_minutes",
    ])
