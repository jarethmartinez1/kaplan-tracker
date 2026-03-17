import hashlib
from datetime import date


def make_external_id(name: str, email: str | None) -> str:
    """Generate a stable external ID from name + email."""
    raw = f"{name or ''}:{email or ''}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def parse_date(text: str | None) -> date | None:
    """Try common date formats."""
    if not text:
        return None
    text = text.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return date.fromisoformat(text) if fmt == "%Y-%m-%d" else __import__("datetime").datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def transform_candidate(
    profile: dict,
    lessons: list[dict],
    lessons_completed: int,
    total_lessons: int,
    quizzes: list[dict],
    total_study_minutes: int | None,
    study_sessions: list[dict],
) -> dict:
    """Transform raw extracted data into structured records for storage."""
    name = profile.get("name") or "Unknown"
    email = profile.get("email")
    enrollment_date = parse_date(profile.get("enrollment_date"))
    external_id = make_external_id(name, email)

    # Process lessons dates
    processed_lessons = []
    for lesson in lessons:
        processed_lessons.append({
            "name": lesson["name"],
            "status": lesson["status"],
            "date_completed": parse_date(lesson.get("date_completed")),
        })

    # Process quizzes
    processed_quizzes = []
    scores = []
    passed_count = 0
    for quiz in quizzes:
        dt = parse_date(quiz.get("date_taken"))
        processed_quizzes.append({
            "name": quiz["name"],
            "score": quiz.get("score"),
            "passing_score": quiz.get("passing_score"),
            "passed": quiz.get("passed"),
            "date_taken": dt,
        })
        if quiz.get("score") is not None:
            scores.append(quiz["score"])
        if quiz.get("passed"):
            passed_count += 1

    # Process study sessions
    processed_sessions = []
    for s in study_sessions:
        processed_sessions.append({
            "date": parse_date(s.get("date")),
            "duration_minutes": s.get("duration_minutes"),
        })

    # Build snapshot
    completion_pct = (lessons_completed / total_lessons * 100) if total_lessons > 0 else 0
    avg_score = sum(scores) / len(scores) if scores else None

    snapshot = {
        "lessons_completed": lessons_completed,
        "total_lessons": total_lessons,
        "completion_pct": round(completion_pct, 1),
        "total_study_minutes": total_study_minutes or 0,
        "avg_quiz_score": round(avg_score, 1) if avg_score is not None else None,
        "quizzes_passed": passed_count,
        "quizzes_total": len(processed_quizzes),
    }

    return {
        "candidate": {
            "external_id": external_id,
            "name": name,
            "email": email,
            "enrollment_date": enrollment_date,
            "total_lessons": total_lessons,
        },
        "lessons": processed_lessons,
        "quizzes": processed_quizzes,
        "study_sessions": processed_sessions,
        "snapshot": snapshot,
    }
