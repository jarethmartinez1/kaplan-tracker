import asyncio

from playwright.async_api import Page, Frame, TimeoutError as PlaywrightTimeout


class PortalAuth:
    """Handles login to the Kaplan admin portal."""

    def __init__(self, page: Page, selectors: dict, username: str, password: str):
        self.page = page
        self.sel = selectors["login"]
        self.username = username
        self.password = password

    async def _find_login_target(self) -> Page | Frame:
        """Find the page or iframe that contains the login form."""
        # Check main page first
        pw_field = await self.page.query_selector("input[type='password']")
        if pw_field:
            return self.page

        # Check all iframes
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            try:
                pw_field = await frame.query_selector("input[type='password']")
                if pw_field:
                    print(f"Login form found in iframe: {frame.url}")
                    return frame
            except Exception:
                continue

        return self.page

    async def _debug_inputs(self, target):
        """Print all input fields for debugging."""
        inputs = await target.query_selector_all("input")
        print(f"Found {len(inputs)} input fields:")
        for inp in inputs:
            name = await inp.get_attribute("name") or ""
            typ = await inp.get_attribute("type") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            inp_id = await inp.get_attribute("id") or ""
            print(f"  <input name='{name}' type='{typ}' id='{inp_id}' placeholder='{placeholder}'>")

    async def _dismiss_cookie_banner(self):
        """Try to dismiss cookie consent banners."""
        for sel in [
            "#onetrust-accept-btn-handler",
            "button:has-text('Accept All')",
            "button:has-text('Accept')",
            ".onetrust-close-btn-handler",
            "#accept-cookies",
        ]:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"Dismissed cookie banner via {sel}")
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue

    async def login(self) -> bool:
        await self.page.goto(self.sel["url"], wait_until="domcontentloaded", timeout=60000)

        # Wait for page to fully render
        try:
            await self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Extra wait for JS-rendered forms
        await asyncio.sleep(3)

        # Dismiss cookie banners
        await self._dismiss_cookie_banner()

        # Find the login form (may be in an iframe)
        target = await self._find_login_target()
        print(f"Using target: {'iframe' if target != self.page else 'main page'}")

        # Debug output
        await self._debug_inputs(target)

        # Also check all frames debug
        print(f"\nTotal frames on page: {len(self.page.frames)}")
        for i, frame in enumerate(self.page.frames):
            frame_inputs = await frame.query_selector_all("input")
            if frame_inputs:
                print(f"  Frame {i} ({frame.url[:80]}): {len(frame_inputs)} inputs")

        # --- Fill username ---
        username_filled = False

        # Try label-based locators on target
        if hasattr(target, 'get_by_label'):
            for label in ["Email Address or Username", "Email", "Username", "Login"]:
                try:
                    locator = target.get_by_label(label)
                    if await locator.count() > 0:
                        await locator.fill(self.username, timeout=5000)
                        username_filled = True
                        print(f"Filled username via label: '{label}'")
                        break
                except Exception:
                    continue

        # Try placeholder-based
        if not username_filled:
            for placeholder_text in ["email", "username", "login"]:
                try:
                    inp = await target.query_selector(f"input[placeholder*='{placeholder_text}' i]")
                    if inp:
                        await inp.fill(self.username)
                        username_filled = True
                        print(f"Filled username via placeholder containing '{placeholder_text}'")
                        break
                except Exception:
                    continue

        # Try CSS selectors
        if not username_filled:
            for selector in self._all_selectors(self.sel["username_field"]):
                try:
                    await target.fill(selector, self.username, timeout=3000)
                    username_filled = True
                    print(f"Filled username via selector: '{selector}'")
                    break
                except Exception:
                    continue

        # Last resort: find first visible text input
        if not username_filled:
            try:
                text_inputs = await target.query_selector_all("input[type='text'], input[type='email'], input:not([type])")
                for inp in text_inputs:
                    if await inp.is_visible():
                        await inp.fill(self.username)
                        username_filled = True
                        print("Filled username via first visible text input")
                        break
            except Exception:
                pass

        if not username_filled:
            print("Could not find username field.")
            return False

        # --- Fill password ---
        password_filled = False
        try:
            pw = await target.query_selector("input[type='password']")
            if pw and await pw.is_visible():
                await pw.fill(self.password)
                password_filled = True
                print("Filled password via input[type='password']")
        except Exception:
            pass

        if not password_filled:
            if hasattr(target, 'get_by_label'):
                try:
                    locator = target.get_by_label("Password")
                    if await locator.count() > 0:
                        await locator.fill(self.password, timeout=5000)
                        password_filled = True
                        print("Filled password via label")
                except Exception:
                    pass

        if not password_filled:
            print("Could not find password field.")
            return False

        # --- Submit ---
        submitted = False
        if hasattr(target, 'get_by_role'):
            try:
                btn = target.get_by_role("button", name="Sign In")
                if await btn.count() > 0:
                    await btn.click(timeout=5000)
                    submitted = True
                    print("Clicked Sign In via role locator")
            except Exception:
                pass

        if not submitted:
            for selector in self._all_selectors(self.sel["submit_button"]):
                try:
                    await target.click(selector, timeout=3000)
                    submitted = True
                    print(f"Clicked submit via selector: '{selector}'")
                    break
                except Exception:
                    continue

        if not submitted:
            print("Could not find submit button.")
            return False

        # Wait for login to complete
        try:
            await self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        try:
            await self.page.wait_for_selector(
                self.sel["success_indicator"],
                timeout=15000,
            )
            return True
        except (PlaywrightTimeout, Exception):
            # Check if URL changed (indicating successful login)
            current_url = self.page.url
            if "/login" not in current_url:
                print(f"URL changed to {current_url} — login likely succeeded.")
                return True
            print("Login submitted but success indicator not found.")
            return False

    def _all_selectors(self, selector_string: str) -> list[str]:
        """Return all CSS selectors from a comma-separated list."""
        return [s.strip() for s in selector_string.split(",") if s.strip()]
