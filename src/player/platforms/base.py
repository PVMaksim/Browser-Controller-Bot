# src/player/platforms/base.py
"""
Abstract base class for all video platforms.
Добавление новой платформы = один файл + наследование от BasePlatform.
Остальной код (controller, keyboards, handlers) не меняется.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from playwright.async_api import Page


@dataclass
class SearchResult:
    """Single video search result returned by platform.search()."""

    title: str
    url: str
    duration: str | None  # "2:49:00" or None if unknown
    thumbnail_url: str | None


class BasePlatform(ABC):
    """
    Abstract interface that every video platform must implement.
    JS-методы (_js_*) реализованы здесь — они работают через HTML5 <video>
    и не зависят от вёрстки конкретного сайта.
    """

    # ------------------------------------------------------------------ #
    # Abstract — must be implemented per platform                         #
    # ------------------------------------------------------------------ #

    @abstractmethod
    async def search(self, page: Page, query: str) -> list[SearchResult]:
        """Search for videos and return up to SEARCH_RESULTS_LIMIT results."""
        ...

    @abstractmethod
    async def open_video(self, page: Page, url: str) -> None:
        """Navigate to a video page and wait for the player to appear."""
        ...

    # ------------------------------------------------------------------ #
    # Universal JS controls — work on any HTML5 <video> element          #
    # Управление через JS-инъекцию не зависит от вёрстки и обновлений UI #
    # ------------------------------------------------------------------ #

    async def play(self, page: Page) -> None:
        """Start or resume playback via HTML5 video API."""
        await page.evaluate("document.querySelector('video').play()")

    async def pause(self, page: Page) -> None:
        """Pause playback via HTML5 video API."""
        await page.evaluate("document.querySelector('video').pause()")

    async def seek_relative(self, page: Page, delta_seconds: int) -> None:
        """
        Seek forward (positive) or backward (negative) by delta seconds.
        Клампим результат в [0, duration] чтобы не выйти за пределы.
        """
        await page.evaluate(f"""() => {{
            const v = document.querySelector('video');
            const target = v.currentTime + {delta_seconds};
            v.currentTime = Math.max(0, Math.min(target, v.duration || target));
        }}""")

    async def seek_absolute(self, page: Page, seconds: int) -> None:
        """Seek to absolute position in seconds."""
        await page.evaluate(f"document.querySelector('video').currentTime = {seconds}")

    async def set_volume(self, page: Page, level: int) -> None:
        """
        Set volume 0–100. Clamps to valid range.
        level=0 не ставит muted=true — только снижает громкость до нуля.
        """
        volume = max(0, min(100, level)) / 100
        await page.evaluate(f"document.querySelector('video').volume = {volume}")

    async def toggle_mute(self, page: Page) -> bool:
        """Toggle mute state. Returns new muted state."""
        return await page.evaluate("""() => {
            const v = document.querySelector('video');
            v.muted = !v.muted;
            return v.muted;
        }""")

    async def get_state(self, page: Page) -> dict:
        """
        Snapshot current player state from HTML5 video element.
        Возвращает dict совместимый с PlayerState.update_from_js().
        """
        return await page.evaluate("""() => {
            const v = document.querySelector('video');
            if (!v) return {current_time: 0, duration: 0, volume: 100, paused: true, muted: false};
            return {
                current_time: Math.floor(v.currentTime),
                duration:     isNaN(v.duration) ? 0 : Math.floor(v.duration),
                volume:       Math.round(v.volume * 100),
                paused:       v.paused,
                muted:        v.muted
            };
        }""")

    async def has_video(self, page: Page) -> bool:
        """Check whether a <video> element exists on the current page."""
        return await page.evaluate(
            "() => document.querySelector('video') !== null"
        )
