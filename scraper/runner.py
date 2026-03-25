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


async def _apply_enrollment_date_filter(page):
    """Set Enrollment Date filter to All Time."""
    enroll_btn = page.get_by_role("button", name="Enrollment Date")
    if await enroll_btn.count() == 0:
        print("  WARNING: No 'Enrollment Date' filter button found.")
        return
    await enroll_btn.click()
    await asyncio.sleep(2)

    all_time = page.get_by_text("All Time", exact=True)
    if await all_time.count() > 0:
        await all_time.click()
        await asyncio.sleep(1)

    apply_btn = page.get_by_role("button", name="Apply")
    if await apply_btn.count() > 0:
        await apply_btn.click()
        print("  Enrollment Date → All Time applied")
        await asyncio.sleep(5)


async def _add_course_status_filter(page):
    """Add Course Status filter via 'Add Filter' and include all statuses."""
    add_filter_btn = page.get_by_role("button", name="Add Filter")
    if await add_filter_btn.count() == 0:
        print("  WARNING: No 'Add Filter' button found.")
        return

    await add_filter_btn.click()
    await asyncio.sleep(2)

    # A dropdown/menu should appear with filter options — look for "Course Status"
    status_option = page.get_by_text("Course Status", exact=False)
    if await status_option.count() > 0:
        await status_option.first.click()
        await asyncio.sleep(2)
        print("  Added 'Course Status' filter")
    else:
        # Debug: list available filter options
        print("  WARNING: 'Course Status' not found in Add Filter menu.")
        menu_items = await page.query_selector_all("[role=menuitem], [role=option], li")
        for item in menu_items[:10]:
            text = (await item.inner_text()).strip()
            if text:
                print(f"    Available filter: '{text}'")
        return

    # Now a Course Status filter should appear — click it to open its options
    await asyncio.sleep(2)
    status_filter_btn = page.get_by_role("button", name="Course Status")
    if await status_filter_btn.count() > 0:
        await status_filter_btn.click()
        await asyncio.sleep(2)
    else:
        print("  WARNING: 'Course Status' button didn't appear after adding.")
        return

    # Select all status checkboxes via JS — MUI hides the real inputs,
    # so we click the MuiFormControlLabel parent elements directly.
    statuses_to_select = [
        "Not Started", "In Progress", "Pending", "Completed",
        "Incomplete", "Active", "Expired",
    ]
    results = await page.evaluate('''(statuses) => {
        const out = [];
        const labels = document.querySelectorAll('.MuiFormControlLabel-root');
        for (const status of statuses) {
            let found = false;
            for (const l of labels) {
                const span = l.querySelector('.MuiTypography-root');
                if (span && span.textContent.trim() === status) {
                    l.click();
                    found = true;
                    break;
                }
            }
            out.push({status, found});
        }
        return out;
    }''', statuses_to_select)
    await asyncio.sleep(1)

    selected_any = False
    for r in results:
        if r["found"]:
            selected_any = True
            print(f"    Selected: {r['status']}")
        else:
            print(f"    Not found: {r['status']}")

    if not selected_any:
        print("  WARNING: Could not select any course status options.")

    # Apply — wait for the button to become enabled after checkbox selection
    if selected_any:
        apply_btn = page.get_by_role("button", name="Apply")
        if await apply_btn.count() > 0:
            try:
                await apply_btn.click(timeout=10000)
                print("  Course Status filter applied")
                await asyncio.sleep(5)
            except Exception:
                # Force click via JS if MUI keeps it disabled
                await page.evaluate('''() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.textContent.trim() === 'Apply' && !b.closest('.onetrust')) {
                            b.disabled = false;
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                print("  Course Status filter applied (via JS)")
                await asyncio.sleep(5)


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

        # Navigate to enrollment report — use the same host as the current page
        current_origin = page.url.split("/portal")[0] if "/portal" in page.url else KAPLAN_PORTAL_URL.rstrip("/")
        report_url = current_origin + ENROLLMENT_REPORT_PATH
        print(f"Navigating to enrollment report: {report_url}")
        await page.goto(report_url, wait_until="domcontentloaded", timeout=60000)

        # Wait for page to be ready
        await asyncio.sleep(3)

        # Configure report filters: All Time
        # NOTE: We intentionally do NOT add a Course Status filter — the default
        # (no status filter) exports all statuses including Completed.
        # Adding a status filter and selecting all options paradoxically
        # excludes Completed rows from the Kaplan portal export.
        print("Configuring report filters...")
        try:
            await _apply_enrollment_date_filter(page)
        except Exception as e:
            print(f"Filter setup warning: {e}")

        # Wait for Export button to become enabled (report must finish loading)
        print("Waiting for Export button to become enabled...")
        export_locator = page.get_by_role("button", name="Export")
        if await export_locator.count() == 0:
            print("ERROR: Could not find Export button.")
            return

        # Wait up to 2 minutes for the button to be enabled
        for _ in range(120):
            is_disabled = await export_locator.get_attribute("disabled")
            if is_disabled is None:
                break
            await asyncio.sleep(1)
        else:
            print("ERROR: Export button still disabled after 2 minutes.")
            return

        print("Clicking Export...")
        async with page.expect_download(timeout=120000) as download_info:
            await export_locator.click()

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
            "first_access_date": row["earliest_access"].date() if pd.notna(row["earliest_access"]) else None,
            "last_access_date": row["latest_access"].date() if pd.notna(row["latest_access"]) else None,
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
                    print("Login successful.")
                    # Navigate to enrollment report
                    current_origin = page.url.split("/portal")[0] if "/portal" in page.url else "https://home.kaplanlearn.com"
                    report_url = current_origin + ENROLLMENT_REPORT_PATH
                    print(f"Navigating to enrollment report: {report_url}")
                    await page.goto(report_url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(5)
                    # Debug: print all buttons and links
                    buttons = await page.query_selector_all("button, a, [role='button']")
                    print(f"\nFound {len(buttons)} clickable elements on report page:")
                    for btn in buttons:
                        text = (await btn.inner_text()).strip()[:60] if await btn.inner_text() else ""
                        tag = await btn.evaluate("el => el.tagName")
                        cls = await btn.get_attribute("class") or ""
                        if text:
                            print(f"  <{tag} class='{cls[:40]}'> {text}")
                else:
                    print("Auto-login failed — log in manually in the browser.")
            except Exception as e:
                print(f"Auto-login error: {e}")
                print("Log in manually in the browser window.")
        else:
            print("No credentials in .env — log in manually in the browser.")

        print("\nBrowser is open. Navigate and inspect elements.")
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
    elif "--headed" in sys.argv:
        asyncio.run(run_export(headless=False))
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
