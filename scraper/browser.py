from playwright.async_api import Browser, BrowserContext, async_playwright


class BrowserManager:
    """Manages Playwright browser lifecycle as an async context manager."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BrowserManager":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self

    async def new_context(self) -> BrowserContext:
        return await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
        )

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
