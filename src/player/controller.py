# src/player/controller.py
"""
PlayerController — unified interface for all media operations.
Не знает о конкретной платформе — работает через BasePlatform.
Управляет: поиском, открытием видео, JS-командами, авто-сохранением позиции,
фоновым пропуском рекламы, историей просмотра.
"""

import asyncio
import asyncio as _asyncio_retry  # alias for test patching
from datetime import datetime

from aiogram import Bot
from loguru import logger
from playwright.async_api import Page

from src.browser.engine import BrowserEngine
from src.config.constants import (
    DEFAULT_MAX_HISTORY_ITEMS,
    DEFAULT_MEDIA_PLATFORM,
    DEFAULT_PLAYER_SEEK_LONG_SEC,
    DEFAULT_PLAYER_SEEK_SHORT_SEC,
    DEFAULT_POSITION_SAVE_INTERVAL_SEC,
    DEFAULT_SEARCH_RESULTS_LIMIT,
)
from src.config.settings import Settings
from src.player.ad_handler import notify_if_ad_playing, watch_and_skip_ads
from src.player.platforms.base import BasePlatform, SearchResult
from src.player.state import PlayerState
from src.player.watch_history import get_position, save_position

# Реестр платформ — добавление новой платформы = одна строка здесь
_PLATFORM_REGISTRY: dict[str, type[BasePlatform]] = {}


def _get_registry() -> dict[str, type[BasePlatform]]:
    """Lazy-build platform registry to avoid circular imports."""
    if not _PLATFORM_REGISTRY:
        from src.player.platforms.rutube import RutubePlatform
        from src.player.platforms.youtube import YouTubePlatform
        from src.player.platforms.vk_video import VKVideoPlatform
        from src.player.platforms.ok_video import OKVideoPlatform
        _PLATFORM_REGISTRY.update({
            "rutube":  RutubePlatform,
            "youtube": YouTubePlatform,
            "vk":      VKVideoPlatform,
            "ok":      OKVideoPlatform,
        })
    return _PLATFORM_REGISTRY


class PlayerController:
    """
    Unified media player controller.
    Один экземпляр на весь жизненный цикл бота.
    """

    def __init__(self, settings: Settings, browser: BrowserEngine, bot: Bot, owner_id: int) -> None:
        self._settings = settings
        self._browser = browser
        self._bot = bot
        self._owner_id = owner_id
        self.state = PlayerState()
        self._auto_save_task: asyncio.Task | None = None
        self._ad_watcher_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # Search                                                               #
    # ------------------------------------------------------------------ #

    async def search(self, query: str, platform: str | None = None) -> list[SearchResult]:
        """
        Search for videos on the specified platform.
        Результаты сохраняются в state.search_results для выбора по номеру кнопки.
        """
        platform = self._resolve_platform(platform)
        page = await self._get_page()
        plat_instance = self._get_platform(platform)

        limit = int(self._settings.get("SEARCH_RESULTS_LIMIT", DEFAULT_SEARCH_RESULTS_LIMIT))
        results = await plat_instance.search(page, query)
        results = results[:limit]

        self.state.search_results = results
        self.state.platform = platform
        logger.info(f"Search '{query}' on {platform}: {len(results)} results")
        return results

    # ------------------------------------------------------------------ #
    # Open video                                                           #
    # ------------------------------------------------------------------ #

    async def open_video(self, index: int) -> dict:
        """
        Open video by 1-based index from last search results.
        Returns dict with title, url, resume_info for handler to display.
        """
        if not self.state.search_results:
            raise ValueError("No search results to open. Run /find first.")
        if index < 1 or index > len(self.state.search_results):
            raise ValueError(f"Index {index} out of range (1–{len(self.state.search_results)})")

        result = self.state.search_results[index - 1]
        return await self._start_video(
            url=result.url,
            title=result.title,
            platform=self.state.platform or DEFAULT_MEDIA_PLATFORM,
        )

    async def open_url_direct(self, url: str, platform: str | None = None) -> dict:
        """Open a video by direct URL (used from watchlist)."""
        platform = self._resolve_platform(platform)
        title = url  # Заголовок неизвестен при прямом открытии
        return await self._start_video(url=url, title=title, platform=platform)

    async def _start_video(self, url: str, title: str, platform: str) -> dict:
        """
        Navigate to video, start ad watcher, start auto-save loop.
        Returns resume info dict for handler.
        """
        page = await self._get_page()
        plat_instance = self._get_platform(platform)

        # Проверяем историю — было ли видео частично просмотрено
        saved = get_position(url)

        await plat_instance.open_video(page, url)

        self.state.is_active = True
        self.state.platform = platform
        self.state.title = title
        self.state.url = url
        self.state.is_paused = False
        self.state.last_command_at = datetime.now()

        # Запускаем фоновые задачи
        self._start_background_tasks(page, url, title, platform)

        # Level 3 реклама — проверяем через секунду после открытия
        asyncio.create_task(self._delayed_ad_check(page))

        return {
            "title":     title,
            "url":       url,
            "platform":  platform,
            "saved":     saved,  # None или dict с position_sec
        }

    # ------------------------------------------------------------------ #
    # Playback controls                                                    #
    # ------------------------------------------------------------------ #

    async def play(self) -> None:
        """Resume playback."""
        page = await self._require_active_page()
        await self._get_platform(self.state.platform).play(page)
        self.state.is_paused = False
        self.state.last_command_at = datetime.now()

    async def pause(self) -> None:
        """Pause playback."""
        page = await self._require_active_page()
        await self._get_platform(self.state.platform).pause(page)
        self.state.is_paused = True
        self.state.last_command_at = datetime.now()

    async def seek(self, delta_seconds: int) -> None:
        """Seek forward (positive) or backward (negative) by delta_seconds."""
        page = await self._require_active_page()
        await self._get_platform(self.state.platform).seek_relative(page, delta_seconds)
        self.state.last_command_at = datetime.now()

    async def set_volume(self, level_or_delta: str) -> int:
        """
        Set or adjust volume.
        level_or_delta: "50" (absolute), "+20" (relative), "-20" (relative)
        Returns new volume level.
        """
        page = await self._require_active_page()
        current = self.state.volume

        if level_or_delta.startswith(("+", "-")):
            new_level = current + int(level_or_delta)
        else:
            new_level = int(level_or_delta)

        new_level = max(0, min(100, new_level))
        await self._get_platform(self.state.platform).set_volume(page, new_level)
        self.state.volume = new_level
        self.state.last_command_at = datetime.now()
        return new_level

    async def toggle_mute(self) -> bool:
        """Toggle mute. Returns new muted state."""
        page = await self._require_active_page()
        new_muted = await self._get_platform(self.state.platform).toggle_mute(page)
        self.state.is_muted = new_muted
        self.state.last_command_at = datetime.now()
        return new_muted

    async def get_current_state(self) -> PlayerState:
        """Sync state with live video element and return it."""
        if self.state.is_active:
            try:
                page = await self._get_page()
                js_state = await self._get_platform(self.state.platform).get_state(page)
                self.state.update_from_js(js_state)
            except Exception as e:
                logger.warning(f"Failed to sync player state: {e}")
        return self.state

    async def close(self) -> None:
        """Stop playback, cancel background tasks, save final position."""
        self._cancel_background_tasks()
        if self.state.is_active and self.state.url:
            # Сохраняем финальную позицию перед закрытием
            save_position(
                url=self.state.url,
                title=self.state.title or "",
                platform=self.state.platform or "",
                position_sec=self.state.position_seconds,
                duration_sec=self.state.duration_seconds,
            )
        self.state.reset()
        await self._browser.close_tab()
        logger.info("Player closed")

    # ------------------------------------------------------------------ #
    # Background tasks                                                     #
    # ------------------------------------------------------------------ #

    def _start_background_tasks(
        self, page: Page, url: str, title: str, platform: str
    ) -> None:
        """Start auto-save and ad-watcher tasks, cancelling previous ones."""
        self._cancel_background_tasks()
        save_interval = int(
            self._settings.get("POSITION_SAVE_INTERVAL_SEC", DEFAULT_POSITION_SAVE_INTERVAL_SEC)
        )
        self._auto_save_task = asyncio.create_task(
            self._auto_save_loop(page, url, title, platform, save_interval),
            name="player_auto_save",
        )
        self._ad_watcher_task = asyncio.create_task(
            watch_and_skip_ads(page, platform),
            name="player_ad_watcher",
        )

    def _cancel_background_tasks(self) -> None:
        for task in (self._auto_save_task, self._ad_watcher_task):
            if task and not task.done():
                task.cancel()

    async def _auto_save_loop(
        self, page: Page, url: str, title: str, platform: str, interval: int
    ) -> None:
        """Save playback position every `interval` seconds."""
        try:
            while self.state.is_active:
                await asyncio.sleep(interval)
                try:
                    js_state = await self._get_platform(platform).get_state(page)
                    self.state.update_from_js(js_state)
                    save_position(
                        url=url,
                        title=title,
                        platform=platform,
                        position_sec=self.state.position_seconds,
                        duration_sec=self.state.duration_seconds,
                    )
                except Exception as e:
                    logger.warning(f"Auto-save failed: {e}")
        except asyncio.CancelledError:
            pass

    async def _delayed_ad_check(self, page: Page) -> None:
        """Check for ads 2 seconds after video opens (Level 3 notification)."""
        await asyncio.sleep(2)
        try:
            await notify_if_ad_playing(page, self._bot, self._owner_id)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    async def _get_page(self):
        """Get or auto-start browser page."""
        if not self._browser.is_running:
            await self._browser.start()
        page = self._browser.get_page()
        assert page is not None
        return page

    async def _require_active_page(self):
        """Get page, raising if player is not active."""
        if not self.state.is_active:
            raise RuntimeError("Плеер не активен. Используй /find для поиска видео.")
        return await self._get_page()

    def _resolve_platform(self, platform: str | None) -> str:
        """Return platform name, falling back to configured default."""
        if platform and platform in _get_registry():
            return platform
        default = self._settings.get("DEFAULT_MEDIA_PLATFORM", DEFAULT_MEDIA_PLATFORM)
        return default if default in _get_registry() else "rutube"

    def _get_platform(self, platform: str | None) -> BasePlatform:
        """Return platform instance from registry."""
        registry = _get_registry()
        name = platform or DEFAULT_MEDIA_PLATFORM
        cls = registry.get(name, registry["rutube"])
        return cls()
