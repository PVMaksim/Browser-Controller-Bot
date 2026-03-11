# src/player/platforms/youtube.py
"""
YouTube platform implementation.
Поиск через страницу YouTube (API требует ключ), управление через HTML5 <video>.
playwright-stealth снижает вероятность блокировки антибот-системой YouTube.
"""

from loguru import logger
from playwright.async_api import Page

from src.player.platforms.base import BasePlatform, SearchResult

_SEARCH_URL = "https://www.youtube.com/results?search_query={query}"


class YouTubePlatform(BasePlatform):
    """YouTube: search via page scraping, playback via HTML5 video."""

    async def search(self, page: Page, query: str) -> list[SearchResult]:
        """
        Search YouTube by navigating to search results page and extracting data.
        YouTube возвращает данные в JSON внутри тега <script> — парсим его.
        """
        from urllib.parse import quote_plus
        search_url = _SEARCH_URL.format(query=quote_plus(query))
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        # Ждём загрузки результатов
        try:
            await page.wait_for_selector("ytd-video-renderer, #contents", timeout=10_000)
        except Exception:
            logger.warning("YouTube: search results did not appear in time")

        # Извлекаем данные из DOM
        results = await page.evaluate("""() => {
            const items = document.querySelectorAll('ytd-video-renderer');
            const out = [];
            items.forEach(item => {
                if (out.length >= 10) return;
                const titleEl = item.querySelector('#video-title');
                const timeEl  = item.querySelector('ytd-thumbnail-overlay-time-status-renderer');
                const href    = titleEl?.href || '';
                if (!href.includes('/watch')) return;
                out.push({
                    title:         titleEl?.textContent?.trim() || 'Без названия',
                    url:           href,
                    duration:      timeEl?.textContent?.trim() || null,
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
        """Navigate to a YouTube video page and wait for the video element."""
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_selector("video.html5-main-video, video", timeout=10_000)
            # YouTube автоматически начинает воспроизведение — небольшая пауза для буферизации
            await page.wait_for_timeout(1500)
            logger.info(f"YouTube video loaded: {url}")
        except Exception:
            logger.warning(f"YouTube: <video> not found on {url}")
