from datetime import date, timedelta

import pandas as pd


def project_completion_date(
    enrollment_date: date | None,
    lessons_completed: int,
    total_lessons: int,
    as_of_date: date | None = None,
) -> date | None:
    """
    Linear projection based on current pace.
    Returns None if projection is not possible.
    """
    as_of_date = as_of_date or date.today()

    if not enrollment_date or lessons_completed <= 0 or total_lessons <= 0:
        return None

    days_elapsed = (as_of_date - enrollment_date).days
    if days_elapsed <= 0:
        return None

    remaining = total_lessons - lessons_completed
    if remaining <= 0:
        return as_of_date  # Already complete

    rate = lessons_completed / days_elapsed  # lessons per day
    days_remaining = remaining / rate
    return as_of_date + timedelta(days=int(days_remaining))


def classify_risk(completion_pct: float, projected_date: date | None, target_date: date | None = None) -> str:
    """Classify candidate as on_track, at_risk, or behind."""
    if completion_pct >= 100:
        return "complete"

    if projected_date is None:
        return "at_risk" if completion_pct < 10 else "unknown"

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
        "id", "name", "email", "enrollment_date", "total_lessons",
        "lessons_completed", "completion_pct", "total_study_minutes",
        "avg_quiz_score", "quizzes_passed", "quizzes_total", "snapshot_date",
    ])

    # Keep only latest snapshot per candidate
    df = df.drop_duplicates(subset=["id"], keep="first")

    # Add projected completion date
    df["projected_date"] = df.apply(
        lambda r: project_completion_date(
            r["enrollment_date"], r["lessons_completed"] or 0, r["total_lessons"] or 0
        ),
        axis=1,
    )

    # Add risk classification
    df["risk_status"] = df.apply(
        lambda r: classify_risk(r["completion_pct"] or 0, r["projected_date"]),
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
