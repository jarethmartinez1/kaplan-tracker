from playwright.async_api import Page, TimeoutError as PlaywrightTimeout


class PortalAuth:
    """Handles login to the Kaplan admin portal."""

    def __init__(self, page: Page, selectors: dict, username: str, password: str):
        self.page = page
        self.sel = selectors["login"]
        self.username = username
        self.password = password

    async def login(self) -> bool:
        await self.page.goto(self.sel["url"], wait_until="domcontentloaded", timeout=60000)

        # Try each selector variant until one works
        for selector in self._all_selectors(self.sel["username_field"]):
            try:
                await self.page.fill(selector, self.username, timeout=3000)
                break
            except Exception:
                continue
        else:
            print(f"Could not find username field.")
            return False

        for selector in self._all_selectors(self.sel["password_field"]):
            try:
                await self.page.fill(selector, self.password, timeout=3000)
                break
            except Exception:
                continue
        else:
            print(f"Could not find password field.")
            return False

        for selector in self._all_selectors(self.sel["submit_button"]):
            try:
                await self.page.click(selector, timeout=3000)
                break
            except Exception:
                continue
        else:
            print(f"Could not find submit button.")
            return False

        try:
            await self.page.wait_for_selector(
                self.sel["success_indicator"],
                timeout=15000,
            )
            return True
        except (PlaywrightTimeout, Exception):
            print("Login submitted but success indicator not found.")
            return False

    def _first_selector(self, selector_string: str) -> str:
        """Use the first CSS selector from a comma-separated list."""
        return selector_string.split(",")[0].strip()

    def _all_selectors(self, selector_string: str) -> list[str]:
        """Return all CSS selectors from a comma-separated list."""
        return [s.strip() for s in selector_string.split(",") if s.strip()]
