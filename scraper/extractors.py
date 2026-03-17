from playwright.async_api import Page


class CandidateExtractor:
    """Extracts candidate data from a detail page using YAML-driven selectors."""

    def __init__(self, page: Page, selectors: dict):
        self.page = page
        self.sel = selectors["candidate_detail"]

    async def extract_profile(self) -> dict:
        return {
            "name": await self._text(self.sel["name"]),
            "email": await self._text(self.sel["email"]),
            "enrollment_date": await self._text(self.sel["enrollment_date"]),
        }

    async def extract_lessons(self) -> tuple[list[dict], int, int]:
        """Returns (lesson_list, completed_count, total_count)."""
        lessons_sel = self.sel["lessons"]
        rows = await self._query_all(lessons_sel["rows"])

        lessons = []
        completed = 0
        for row in rows:
            name = await self._row_text(row, lessons_sel["lesson_name"])
            status = await self._row_text(row, lessons_sel["lesson_status"])
            date_done = await self._row_text(row, lessons_sel["lesson_date_completed"])

            if status and "complet" in status.lower():
                completed += 1

            lessons.append({
                "name": name or "Unknown",
                "status": self._normalize_status(status),
                "date_completed": date_done,
            })

        total = len(lessons)

        # Try to get counts from summary elements if available
        total_text = await self._text(lessons_sel.get("total_count", ""))
        completed_text = await self._text(lessons_sel.get("completed_count", ""))
        if total_text:
            total = self._parse_int(total_text) or total
        if completed_text:
            completed = self._parse_int(completed_text) or completed

        return lessons, completed, total

    async def extract_quizzes(self) -> list[dict]:
        quizzes_sel = self.sel["quizzes"]
        rows = await self._query_all(quizzes_sel["rows"])

        quizzes = []
        for row in rows:
            name = await self._row_text(row, quizzes_sel["quiz_name"])
            score_text = await self._row_text(row, quizzes_sel["score"])
            date_taken = await self._row_text(row, quizzes_sel["date_taken"])
            passing_text = await self._row_text(row, quizzes_sel.get("passing_score", ""))

            score = self._parse_float(score_text)
            passing = self._parse_float(passing_text)

            quizzes.append({
                "name": name or "Unknown",
                "score": score,
                "passing_score": passing,
                "passed": score >= passing if score is not None and passing is not None else None,
                "date_taken": date_taken,
            })

        return quizzes

    async def extract_study_time(self) -> tuple[int | None, list[dict]]:
        """Returns (total_minutes, session_list)."""
        time_sel = self.sel["study_time"]
        total_text = await self._text(time_sel["total_hours"])
        total_minutes = self._parse_duration(total_text)

        sessions = []
        rows = await self._query_all(time_sel.get("session_rows", ""))
        for row in rows:
            sdate = await self._row_text(row, time_sel["session_date"])
            sdur = await self._row_text(row, time_sel["session_duration"])
            sessions.append({
                "date": sdate,
                "duration_minutes": self._parse_duration(sdur),
            })

        return total_minutes, sessions

    # --- Helpers ---

    async def _text(self, selector: str) -> str | None:
        if not selector:
            return None
        first = selector.split(",")[0].strip()
        try:
            el = await self.page.query_selector(first)
            return (await el.inner_text()).strip() if el else None
        except Exception:
            return None

    async def _query_all(self, selector: str) -> list:
        if not selector:
            return []
        first = selector.split(",")[0].strip()
        try:
            return await self.page.query_selector_all(first)
        except Exception:
            return []

    async def _row_text(self, row, selector: str) -> str | None:
        if not selector:
            return None
        first = selector.split(",")[0].strip()
        try:
            el = await row.query_selector(first)
            return (await el.inner_text()).strip() if el else None
        except Exception:
            return None

    @staticmethod
    def _normalize_status(raw: str | None) -> str:
        if not raw:
            return "not_started"
        lower = raw.lower()
        if "complet" in lower:
            return "completed"
        if "progress" in lower or "start" in lower:
            return "in_progress"
        return "not_started"

    @staticmethod
    def _parse_int(text: str | None) -> int | None:
        if not text:
            return None
        digits = "".join(c for c in text if c.isdigit())
        return int(digits) if digits else None

    @staticmethod
    def _parse_float(text: str | None) -> float | None:
        if not text:
            return None
        cleaned = "".join(c for c in text if c.isdigit() or c == ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _parse_duration(text: str | None) -> int | None:
        """Parse duration text like '2h 30m', '150 min', '2.5 hours' into minutes."""
        if not text:
            return None
        lower = text.lower()
        minutes = 0
        if "h" in lower:
            parts = lower.replace("hours", "h").replace("hour", "h").split("h")
            hours = CandidateExtractor._parse_float(parts[0])
            if hours:
                minutes += int(hours * 60)
            if len(parts) > 1:
                m = CandidateExtractor._parse_float(parts[1])
                if m:
                    minutes += int(m)
        else:
            val = CandidateExtractor._parse_float(lower)
            if val:
                minutes = int(val)
        return minutes if minutes > 0 else None
