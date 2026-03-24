from datetime import date, timedelta

import pandas as pd


def project_completion_date(
    first_access_date: date | None,
    last_access_date: date | None,
    lessons_completed: int,
    total_lessons: int,
) -> date | None:
    """
    Linear projection based on pace between first and last access.
    Uses the active study window (first_access → last_access) rather than
    enrollment date, which may predate actual study activity by years.
    Returns None if projection is not possible.
    """
    if not first_access_date or not last_access_date:
        return None
    if lessons_completed <= 0 or total_lessons <= 0:
        return None

    remaining = total_lessons - lessons_completed
    if remaining <= 0:
        return last_access_date  # Already complete

    days_active = (last_access_date - first_access_date).days
    if days_active <= 0:
        return None  # Single-day access, can't extrapolate

    rate = lessons_completed / days_active  # lessons per day
    days_remaining = remaining / rate
    return last_access_date + timedelta(days=int(days_remaining))


INACTIVE_THRESHOLD_DAYS = 90
OVERDUE_INACTIVE_DAYS = 120
TARGET_WEEKS_FROM_START = 4


def classify_risk(
    completion_pct: float,
    projected_date: date | None,
    last_access_date: date | None,
    target_date: date | None = None,
) -> str:
    """Classify candidate status."""
    if completion_pct >= 100:
        return "complete"

    if completion_pct == 0:
        return "not_started"

    # Check inactivity
    days_since_access = (date.today() - last_access_date).days if last_access_date else None
    inactive = days_since_access is not None and days_since_access > INACTIVE_THRESHOLD_DAYS

    if projected_date is None:
        return "inactive" if inactive else "unknown"

    # Projected date is in the past — they didn't finish on time
    if projected_date < date.today() and inactive:
        # Overdue 120+ days past projected date → inactive
        days_overdue = (date.today() - projected_date).days
        if days_overdue > OVERDUE_INACTIVE_DAYS:
            return "inactive"
        return "overdue"

    if target_date and projected_date > target_date:
        return "behind"

    if completion_pct >= 60:
        return "on_track"
    elif completion_pct >= 30:
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

    # Add projected completion date
    df["projected_date"] = df.apply(
        lambda r: project_completion_date(
            r["first_access_date"], r["last_access_date"],
            r["lessons_completed"] or 0, r["total_lessons"] or 0,
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
            r["completion_pct"] or 0, r["projected_date"],
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
