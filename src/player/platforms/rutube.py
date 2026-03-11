# src/player/platforms/rutube.py
"""
RuTube platform implementation.
Поиск через публичный API RuTube, управление через HTML5 <video>.
Возможна captcha — обходим через playwright-stealth (подключается в browser/engine).
"""

import json

from loguru import logger
from playwright.async_api import Page

from src.player.platforms.base import BasePlatform, SearchResult

_SEARCH_URL = "https://rutube.ru/api/search/video/?query={query}&page=1&page_size=10"
_SEARCH_PAGE_URL = "https://rutube.ru/search/?query={query}"


class RutubePlatform(BasePlatform):
    """RuTube: search via API, playback via HTML5 video."""

    async def search(self, page: Page, query: str) -> list[SearchResult]:
        """
        Search RuTube using their public search API.
        Fallback на поиск через страницу если API недоступен.
        """
        from urllib.parse import quote_plus
        api_url = _SEARCH_URL.format(query=quote_plus(query))

        try:
            results = await self._search_via_api(page, api_url)
            if results:
                return results
        except Exception as e:
            logger.warning(f"RuTube API search failed, trying page search: {e}")

        return await self._search_via_page(page, query)

    async def _search_via_api(self, page: Page, api_url: str) -> list[SearchResult]:
        """Fetch search results from RuTube JSON API."""
        response = await page.evaluate(f"""async () => {{
            const r = await fetch('{api_url}', {{
                headers: {{'Accept': 'application/json'}}
            }});
            return r.ok ? await r.json() : null;
        }}""")

        if not response or "results" not in response:
            return []

        results = []
        for item in response["results"][:10]:
            duration_secs = item.get("duration", 0)
            results.append(SearchResult(
                title=item.get("title", "Без названия"),
                url=f"https://rutube.ru/video/{item.get('id', '')}/",
                duration=_fmt_duration(duration_secs) if duration_secs else None,
                thumbnail_url=item.get("thumbnail_url"),
            ))
        return results

    async def _search_via_page(self, page: Page, query: str) -> list[SearchResult]:
        """Scrape search results from RuTube search page (fallback)."""
        from urllib.parse import quote_plus
        await page.goto(
            _SEARCH_PAGE_URL.format(query=quote_plus(query)),
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        # Ждём появления результатов
        try:
            await page.wait_for_selector(
                "[class*='VideoCard'], [class*='video-card']",
                timeout=8_000,
            )
        except Exception:
            logger.warning("RuTube: search results did not appear")
            return []

        return await page.evaluate("""() => {
            const cards = document.querySelectorAll(
                "[class*='VideoCard_title'], [class*='video-card__title']"
            );
            const links = document.querySelectorAll(
                "a[href*='/video/']"
            );
            const results = [];
            links.forEach((link, i) => {
                if (i >= 10) return;
                const title = link.querySelector('h3, p, span')?.textContent?.trim()
                    || link.textContent?.trim() || 'Без названия';
                results.push({
                    title: title,
                    url: link.href,
                    duration: null,
                    thumbnail_url: null
                });
            });
            return results;
        }""")

    async def open_video(self, page: Page, url: str) -> None:
        """Navigate to a RuTube video page and wait for the video player."""
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_selector("video", timeout=10_000)
            logger.info(f"RuTube video loaded: {url}")
        except Exception:
            logger.warning(f"RuTube: <video> not found on {url}")


def _fmt_duration(seconds: int) -> str:
    """Format duration seconds as H:MM:SS or M:SS."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
