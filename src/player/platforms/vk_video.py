# src/player/platforms/vk_video.py
"""
VK Video platform implementation.
Поиск через VK публичный API (без авторизации для публичных видео).
Авторизованный контент доступен через сохранённый профиль браузера.
"""

from loguru import logger
from playwright.async_api import Page

from src.player.platforms.base import BasePlatform, SearchResult

_SEARCH_URL = "https://vk.com/video?q={query}&section=search"


class VKVideoPlatform(BasePlatform):
    """VK Video: search via page, playback via HTML5 video."""

    async def search(self, page: Page, query: str) -> list[SearchResult]:
        """Search VK Video by navigating to search page."""
        from urllib.parse import quote_plus
        search_url = _SEARCH_URL.format(query=quote_plus(query))
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        try:
            await page.wait_for_selector(
                ".video_item, .VideoCard, [class*='VideoCard']",
                timeout=10_000,
            )
        except Exception:
            logger.warning("VK Video: search results not found")
            return []

        results = await page.evaluate("""() => {
            const items = document.querySelectorAll('.video_item, [class*="VideoCard"]');
            const out = [];
            items.forEach(item => {
                if (out.length >= 10) return;
                const titleEl = item.querySelector('.video_item__title, [class*="title"]');
                const link    = item.querySelector('a[href*="/video"]');
                const dur     = item.querySelector('.video_item__duration, [class*="duration"]');
                if (!link) return;
                out.push({
                    title:    titleEl?.textContent?.trim() || 'Без названия',
                    url:      'https://vk.com' + (link.getAttribute('href') || ''),
                    duration: dur?.textContent?.trim() || null,
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
        """Navigate to VK Video page and wait for video player."""
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            await page.wait_for_selector("video", timeout=10_000)
            logger.info(f"VK Video loaded: {url}")
        except Exception:
            logger.warning(f"VK Video: <video> not found on {url}")
