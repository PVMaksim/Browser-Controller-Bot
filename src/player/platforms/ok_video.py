# src/player/platforms/ok_video.py
"""
Odnoklassniki (OK.ru) video platform implementation.
Архитектура схожа с VK — поиск через страницу, управление через HTML5 <video>.
"""

from loguru import logger
from playwright.async_api import Page

from src.player.platforms.base import BasePlatform, SearchResult

_SEARCH_URL = "https://ok.ru/video?q={query}"


class OKVideoPlatform(BasePlatform):
    """Odnoklassniki Video: search via page, playback via HTML5 video."""

    async def search(self, page: Page, query: str) -> list[SearchResult]:
        """Search OK.ru video by navigating to search page."""
        from urllib.parse import quote_plus
        search_url = _SEARCH_URL.format(query=quote_plus(query))
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        try:
            await page.wait_for_selector(
                ".video-card, [class*='VideoCard'], .vid-card",
                timeout=10_000,
            )
        except Exception:
            logger.warning("OK Video: search results not found")
            return []

        results = await page.evaluate("""() => {
            const items = document.querySelectorAll('.video-card, .vid-card, [class*="VideoCard"]');
            const out = [];
            items.forEach(item => {
                if (out.length >= 10) return;
                const titleEl = item.querySelector('span[class*="title"], .vid-card_n');
                const link    = item.querySelector('a[href*="/video/"]');
                const dur     = item.querySelector('[class*="duration"], .vid-card_duration');
                if (!link) return;
                const href = link.href || link.getAttribute('href') || '';
                const fullUrl = href.startsWith('http') ? href : 'https://ok.ru' + href;
                out.push({
                    title:         titleEl?.textContent?.trim() || 'Без названия',
                    url:           fullUrl,
                    duration:      dur?.textContent?.trim() || null,
                    thumbnail_url: item.querySelector('img')?.src || null
                });
            });
            return out;
        }""")

        return [
            SearchResult(
                title=r["title"],
                url=r["url"],
                duration=r["duration"],
                thumbnail_url=r["thumbnail_url"],
            )
            for r in (results or [])
        ]

    async def open_video(self, page: Page, url: str) -> None:
        """Navigate to OK.ru video page and wait for video player."""
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_selector("video", timeout=10_000)
            logger.info(f"OK Video loaded: {url}")
        except Exception:
            logger.warning(f"OK Video: <video> not found on {url}")
