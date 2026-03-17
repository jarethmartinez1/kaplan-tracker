from datetime import date

from sqlalchemy.orm import Session

from data.models import (
    Candidate,
    LessonProgress,
    ProgressSnapshot,
    QuizScore,
    StudySession,
)


def upsert_candidate(session: Session, data: dict) -> Candidate:
    """Insert or update a candidate by external_id."""
    candidate = (
        session.query(Candidate)
        .filter_by(external_id=data["external_id"])
        .first()
    )
    if candidate:
        for key, val in data.items():
            if key != "external_id" and val is not None:
                setattr(candidate, key, val)
    else:
        candidate = Candidate(**data)
        session.add(candidate)
    session.flush()
    return candidate


def store_lessons(session: Session, candidate_id: int, lessons: list[dict]):
    today = date.today()
    for lesson in lessons:
        exists = (
            session.query(LessonProgress)
            .filter_by(
                candidate_id=candidate_id,
                lesson_name=lesson["name"],
                scraped_at=today,
            )
            .first()
        )
        if not exists:
            session.add(
                LessonProgress(
                    candidate_id=candidate_id,
                    lesson_name=lesson["name"],
                    status=lesson.get("status"),
                    date_completed=lesson.get("date_completed"),
                    scraped_at=today,
                )
            )


def store_quizzes(session: Session, candidate_id: int, quizzes: list[dict]):
    for quiz in quizzes:
        exists = (
            session.query(QuizScore)
            .filter_by(
                candidate_id=candidate_id,
                quiz_name=quiz["name"],
                date_taken=quiz.get("date_taken"),
            )
            .first()
        )
        if not exists:
            session.add(
                QuizScore(
                    candidate_id=candidate_id,
                    quiz_name=quiz["name"],
                    score=quiz.get("score"),
                    passing_score=quiz.get("passing_score"),
                    passed=quiz.get("passed"),
                    date_taken=quiz.get("date_taken"),
                    scraped_at=date.today(),
                )
            )


def store_study_sessions(session: Session, candidate_id: int, study_sessions: list[dict]):
    for s in study_sessions:
        exists = (
            session.query(StudySession)
            .filter_by(
                candidate_id=candidate_id,
                session_date=s.get("date"),
            )
            .first()
        )
        if not exists:
            session.add(
                StudySession(
                    candidate_id=candidate_id,
                    session_date=s.get("date"),
                    duration_minutes=s.get("duration_minutes"),
                    scraped_at=date.today(),
                )
            )


def store_snapshot(session: Session, candidate_id: int, snapshot_data: dict):
    today = date.today()
    existing = (
        session.query(ProgressSnapshot)
        .filter_by(candidate_id=candidate_id, snapshot_date=today)
        .first()
    )
    if existing:
        for key, val in snapshot_data.items():
            setattr(existing, key, val)
    else:
        session.add(
            ProgressSnapshot(
                candidate_id=candidate_id,
                snapshot_date=today,
                **snapshot_data,
            )
        )
