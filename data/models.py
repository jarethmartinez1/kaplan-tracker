from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String, unique=True)
    name = Column(String, nullable=False)
    email = Column(String)
    enrollment_date = Column(Date)
    first_access_date = Column(Date)
    last_access_date = Column(Date)
    total_lessons = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lessons = relationship("LessonProgress", back_populates="candidate")
    quizzes = relationship("QuizScore", back_populates="candidate")
    sessions = relationship("StudySession", back_populates="candidate")
    snapshots = relationship("ProgressSnapshot", back_populates="candidate")


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("candidate_id", "lesson_name", "scraped_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    lesson_name = Column(String, nullable=False)
    status = Column(String)  # completed, in_progress, not_started
    date_completed = Column(Date)
    scraped_at = Column(Date, default=date.today)

    candidate = relationship("Candidate", back_populates="lessons")


class QuizScore(Base):
    __tablename__ = "quiz_scores"
    __table_args__ = (
        UniqueConstraint("candidate_id", "quiz_name", "date_taken"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    quiz_name = Column(String, nullable=False)
    score = Column(Float)
    passing_score = Column(Float)
    passed = Column(Boolean)
    date_taken = Column(Date)
    scraped_at = Column(Date, default=date.today)

    candidate = relationship("Candidate", back_populates="quizzes")


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    session_date = Column(Date)
    duration_minutes = Column(Integer)
    scraped_at = Column(Date, default=date.today)

    candidate = relationship("Candidate", back_populates="sessions")


class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"
    __table_args__ = (
        UniqueConstraint("candidate_id", "snapshot_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False, default=date.today)
    lessons_completed = Column(Integer, default=0)
    total_lessons = Column(Integer, default=0)
    completion_pct = Column(Float, default=0.0)
    total_study_minutes = Column(Integer, default=0)
    avg_quiz_score = Column(Float)
    quizzes_passed = Column(Integer, default=0)
    quizzes_total = Column(Integer, default=0)

    candidate = relationship("Candidate", back_populates="snapshots")
