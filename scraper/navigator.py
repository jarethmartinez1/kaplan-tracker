from playwright.async_api import Page, TimeoutError as PlaywrightTimeout


class PortalNavigator:
    """Navigates the Kaplan admin portal and iterates over candidates."""

    def __init__(self, page: Page, selectors: dict):
        self.page = page
        self.nav = selectors["navigation"]

    async def go_to_candidates(self):
        """Navigate to the candidates list page."""
        menu_sel = self.nav["candidates_menu"]
        try:
            await self.page.click(menu_sel.split(",")[0].strip(), timeout=5000)
            await self.page.wait_for_load_state("networkidle")
        except PlaywrightTimeout:
            # Fallback: navigate directly by URL
            base = self.page.url.rstrip("/")
            url = base + self.nav["candidates_list_url"]
            await self.page.goto(url, wait_until="networkidle")

    async def get_candidate_links(self) -> list[str]:
        """Collect all candidate detail URLs across pages."""
        links = []
        while True:
            row_sel = self.nav["candidate_row"].split(",")[0].strip()
            try:
                await self.page.wait_for_selector(row_sel, timeout=10000)
            except PlaywrightTimeout:
                break

            link_sel = self.nav["candidate_link"].split(",")[0].strip()
            elements = await self.page.query_selector_all(link_sel)
            for el in elements:
                href = await el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        origin = self.page.url.split("/")[0:3]
                        href = "/".join(origin) + href
                    links.append(href)

            # Try next page
            if not await self._go_next_page():
                break

        return links

    async def _go_next_page(self) -> bool:
        no_more_sel = self.nav["no_more_pages"].split(",")[0].strip()
        try:
            disabled = await self.page.query_selector(no_more_sel)
            if disabled:
                return False
        except Exception:
            pass

        next_sel = self.nav["next_page_button"].split(",")[0].strip()
        try:
            btn = await self.page.query_selector(next_sel)
            if not btn:
                return False
            await btn.click()
            await self.page.wait_for_load_state("networkidle")
            return True
        except Exception:
            return False
