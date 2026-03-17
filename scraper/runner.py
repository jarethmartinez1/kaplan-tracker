import asyncio
import sys
from datetime import date
from pathlib import Path

from config.settings import (
    BASE_DIR,
    KAPLAN_PASSWORD,
    KAPLAN_USERNAME,
    KAPLAN_PORTAL_URL,
    load_selectors,
)
from data.database import get_session, init_db
from data.store import store_quizzes, store_snapshot, upsert_candidate
from scraper.auth import PortalAuth
from scraper.browser import BrowserManager
from scraper.excel_parser import aggregate_per_candidate, parse_kaplan_excel

# URL patterns from Kaplan portal
ENROLLMENT_REPORT_PATH = "/portal/klre/company/7007557/enrollmentreport"


async def run_export(headless: bool = True, excel_path: str | None = None):
    """Log in, export Excel from enrollment report, parse, and store in DB."""
    engine = init_db()
    session = get_session(engine)

    if excel_path:
        # Skip browser — use a previously downloaded file
        print(f"Using existing Excel file: {excel_path}")
        _import_excel(session, excel_path)
        return

    selectors = load_selectors()
    downloads_dir = BASE_DIR / "downloads"
    downloads_dir.mkdir(exist_ok=True)

    print("Launching browser...")
    async with BrowserManager(headless=headless) as bm:
        context = await bm.new_context()
        # Set up download handling
        page = await context.new_page()

        # Login
        print("Logging in to Kaplan...")
        auth = PortalAuth(page, selectors, KAPLAN_USERNAME, KAPLAN_PASSWORD)
        if not await auth.login():
            print("ERROR: Login failed. Check credentials and selectors.")
            return

        print("Login successful.")

        # Navigate to enrollment report
        report_url = KAPLAN_PORTAL_URL.rstrip("/") + ENROLLMENT_REPORT_PATH
        print(f"Navigating to enrollment report: {report_url}")
        await page.goto(report_url, wait_until="domcontentloaded", timeout=60000)

        # Wait for page to be ready
        await asyncio.sleep(3)

        # Set filters to "All Time" for both Enrollment and Completion Date
        print("Setting filters to All Time...")
        try:
            # Click Enrollment Date dropdown and select All Time
            enrollment_filter = await page.query_selector("text=Enrollment Date")
            if enrollment_filter:
                await enrollment_filter.click()
                await asyncio.sleep(1)
                all_time_btn = await page.query_selector("text=All Time")
                if all_time_btn:
                    await all_time_btn.click()
                    await asyncio.sleep(1)

            # Click Completion Date dropdown and select All Time
            completion_filter = await page.query_selector("text=Completion Date")
            if completion_filter:
                await completion_filter.click()
                await asyncio.sleep(1)
                all_time_btn = await page.query_selector("text=All Time")
                if all_time_btn:
                    await all_time_btn.click()
                    await asyncio.sleep(2)
        except Exception as e:
            print(f"Filter setup warning: {e}")
            print("Proceeding with default filters...")

        # Wait for report to load
        print("Waiting for report data to load...")
        await asyncio.sleep(5)

        # Click Export button and wait for download
        print("Clicking Export...")
        async with page.expect_download(timeout=60000) as download_info:
            export_btn = await page.query_selector("text=Export")
            if not export_btn:
                export_btn = await page.query_selector("[class*='export'], button:has-text('Export')")
            if export_btn:
                await export_btn.click()
            else:
                print("ERROR: Could not find Export button.")
                return

        download = await download_info.value
        save_path = downloads_dir / f"kaplan_export_{date.today().isoformat()}.xlsx"
        await download.save_as(save_path)
        print(f"Downloaded: {save_path}")

    # Parse and import
    _import_excel(session, save_path)


def _import_excel(session, file_path):
    """Parse Excel and import into database."""
    print(f"\nParsing Excel file...")
    df = parse_kaplan_excel(file_path)
    print(f"Found {len(df)} course enrollments for {df['Name'].nunique()} candidates.")

    # Aggregate per candidate
    candidates_agg = aggregate_per_candidate(df)

    print("Importing into database...")
    for _, row in candidates_agg.iterrows():
        # Upsert candidate
        candidate_data = {
            "external_id": str(row["External ID"]),
            "name": row["Name"],
            "email": row["Email"],
            "enrollment_date": row["earliest_enrollment"].date() if pd.notna(row["earliest_enrollment"]) else None,
            "total_lessons": int(row["total_courses"]),
        }
        candidate = upsert_candidate(session, candidate_data)

        # Store quiz scores (one per course)
        candidate_courses = df[df["External ID"] == row["External ID"]]
        quizzes = []
        for _, course in candidate_courses.iterrows():
            if pd.notna(course["Score"]):
                quizzes.append({
                    "name": course["Course Name"],
                    "score": float(course["Score"]),
                    "passing_score": 70.0,  # Standard Kaplan passing score
                    "passed": float(course["Score"]) >= 70,
                    "date_taken": course["Completion Date"].date() if pd.notna(course["Completion Date"]) else None,
                })
        store_quizzes(session, candidate.id, quizzes)

        # Store snapshot
        snapshot = {
            "lessons_completed": int(row["completed_courses"]),
            "total_lessons": int(row["total_courses"]),
            "completion_pct": float(row["completion_pct"]),
            "total_study_minutes": int(row["total_seat_minutes"]) if pd.notna(row["total_seat_minutes"]) else 0,
            "avg_quiz_score": round(float(row["avg_score"]), 1) if pd.notna(row["avg_score"]) else None,
            "quizzes_passed": len([q for q in quizzes if q.get("passed")]),
            "quizzes_total": len(quizzes),
        }
        store_snapshot(session, candidate.id, snapshot)

    session.commit()
    print(f"\nDone. Imported {len(candidates_agg)} candidates into database.")


async def run_discover():
    """Open a headed browser for manual portal inspection."""
    selectors = load_selectors()

    print("Opening browser in discovery mode...")
    print("After login, navigate the portal and inspect elements.")
    print("Update config/selectors.yaml with the correct selectors.")
    print("Press Ctrl+C in terminal when done.\n")

    async with BrowserManager(headless=False) as bm:
        context = await bm.new_context()
        page = await context.new_page()

        login_url = selectors["login"]["url"]
        print(f"Navigating to {login_url}")

        try:
            await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Navigation warning: {e}")
            print("Page may still be loading — that's OK in discovery mode.")

        if KAPLAN_USERNAME and KAPLAN_PASSWORD:
            try:
                auth = PortalAuth(page, selectors, KAPLAN_USERNAME, KAPLAN_PASSWORD)
                success = await auth.login()
                if success:
                    print("Login successful. Browser is open for inspection.")
                else:
                    print("Auto-login failed — log in manually in the browser.")
            except Exception as e:
                print(f"Auto-login error: {e}")
                print("Log in manually in the browser window.")
        else:
            print("No credentials in .env — log in manually in the browser.")

        print("\nBrowser is open. Navigate and inspect elements.")
        print("Right-click elements -> Inspect to find CSS selectors.")
        print("Press Ctrl+C in terminal when done.")

        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nClosing browser.")


# Need pandas import for _import_excel
import pandas as pd


def main():
    if "--discover" in sys.argv:
        asyncio.run(run_discover())
    elif "--file" in sys.argv:
        # Import from an existing Excel file
        idx = sys.argv.index("--file")
        if idx + 1 < len(sys.argv):
            file_path = sys.argv[idx + 1]
            asyncio.run(run_export(excel_path=file_path))
        else:
            print("Usage: python scripts/run_scraper.py --file <path_to_excel>")
    else:
        asyncio.run(run_export())
