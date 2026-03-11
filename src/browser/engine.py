# src/browser/engine.py
"""
Playwright browser engine with isolated persistent profile.
Изолированный профиль — обязательное требование безопасности:
история, куки и данные сайтов не смешиваются с личным браузером пользователя.

playwright-stealth применяется к каждой новой странице — маскирует
автоматизацию от антибот-систем RuTube и YouTube.
"""

from pathlib import Path
from urllib.parse import quote_plus

from loguru import logger
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from src.browser.antibot import CHROMIUM_ANTIBOT_ARGS, inject_extra_patches
import src.browser.stealth as _stealth
from src.config.constants import (
    DEFAULT_BROWSER_HEADLESS,
    DEFAULT_BROWSER_TYPE,
    SEARCH_ENGINES,
)
from src.config.paths import get_browser_profile_dir
from src.config.settings import Settings

# User-agent выбирается случайно при каждом старте браузера (пул в antibot.py)


class BrowserEngine:
    """
    Manages a Playwright browser with a persistent isolated profile.

    Использует launch_persistent_context — единый вызов создаёт браузер
    с конкретной папкой профиля. Состояние (авторизации, cookies) сохраняется
    между сессиями внутри изолированного профиля.

    playwright-stealth применяется при создании каждой страницы через
    _setup_page() — применяет JS-патчи и stealth к каждой странице.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._stealth_available: bool = False
        self._browser_type: str = "chromium"

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """
        Launch browser with isolated persistent profile.
        Создаёт папку профиля если её нет. Безопасно вызывать повторно.
        """
        if self.is_running:
            logger.debug("Browser already running, skipping start")
            return

        profile_dir: Path = get_browser_profile_dir()
        profile_dir.mkdir(parents=True, exist_ok=True)

        browser_type_name: str = self._settings.get("BROWSER_TYPE", DEFAULT_BROWSER_TYPE)
        headless_raw: str = self._settings.get(
            "BROWSER_HEADLESS", str(DEFAULT_BROWSER_HEADLESS)
        )
        headless: bool = headless_raw.lower() not in ("false", "0", "no")

        # Проверяем доступность playwright-stealth один раз при старте
        self._stealth_available = _stealth.is_available()
        if self._stealth_available:
            logger.info("playwright-stealth: available (per-browser config enabled)")
        else:
            logger.warning(
                "playwright-stealth not installed — antibot protection reduced. "
                "Install: pip install playwright-stealth"
            )

        self._playwright = await async_playwright().start()

        match browser_type_name.lower():
            case "firefox":
                launcher = self._playwright.firefox
            case "webkit":
                launcher = self._playwright.webkit
            case _:
                launcher = self._playwright.chromium

        # Фиксируем тип браузера и соответствующий UA на всю сессию
        self._browser_type = browser_type_name.lower()
        session_ua = _stealth.get_user_agent(self._browser_type)

        self._context = await launcher.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            user_agent=session_ua,
            viewport={"width": 1280, "height": 800},
            locale="ru-RU",
            args=CHROMIUM_ANTIBOT_ARGS if browser_type_name.lower() in ("chromium", "chrome") else [],
        )

        # Применяем stealth к уже открытым страницам и ко всем новым
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        await self._setup_page(self._page)

        # Новые страницы тоже получают stealth
        self._context.on("page", lambda page: _schedule_new_page(page, self._browser_type, self._stealth_available))

        logger.info(
            f"Browser started. type={browser_type_name}, "
            f"headless={headless}, stealth={self._stealth_available}, "
            f"ua={session_ua[:40]}..., profile={profile_dir}"
        )

    async def stop(self) -> None:
        """Close browser context and playwright instance."""
        try:
            if self._context:
                await self._context.close()
                logger.info("Browser context closed")
        except Exception as e:
            logger.error(f"Error closing browser context: {e}")
        finally:
            self._context = None
            self._page = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

    @property
    def is_running(self) -> bool:
        """Return True if browser is active and a page is available."""
        return self._context is not None and self._page is not None

    # ------------------------------------------------------------------ #
    # State                                                                #
    # ------------------------------------------------------------------ #

    def get_current_url(self) -> str | None:
        """Return current page URL, or None if browser is not active."""
        if self._page:
            try:
                url = self._page.url
                return url if url and url != "about:blank" else None
            except Exception:
                return None
        return None

    def get_page(self) -> Page | None:
        """Return the active Playwright Page instance."""
        return self._page

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    async def open_url(self, url: str) -> None:
        """Navigate to the given URL and wait for DOM content to load."""
        page = await self._ensure_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        logger.info(f"Opened: {url} → actual: {page.url}")

    async def take_screenshot(self) -> bytes:
        """Capture visible area screenshot as PNG bytes."""
        page = await self._ensure_page()
        screenshot: bytes = await page.screenshot(type="png", full_page=False)
        logger.info(f"Screenshot: {len(screenshot):,} bytes")
        return screenshot

    async def close_tab(self) -> None:
        """
        Close current page and open a fresh blank page.
        Не закрываем весь браузер — только активную вкладку.
        """
        if not self.is_running or self._context is None:
            logger.warning("close_tab: browser not running, nothing to close")
            return

        if self._page:
            await self._page.close()

        self._page = await self._context.new_page()
        await self._setup_page(self._page)
        logger.info("Tab closed, blank page ready")

    async def search(self, query: str) -> None:
        """Perform web search using the engine configured in settings."""
        engine: str = self._settings.get("SEARCH_ENGINE", "google").lower()
        base_url: str = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
        search_url = base_url + quote_plus(query)
        await self.open_url(search_url)
        logger.info(f"Search: engine={engine}, query='{query}'")

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _ensure_page(self) -> Page:
        """Ensure browser is started and return active page."""
        if not self.is_running:
            logger.info("Browser not running — auto-starting")
            await self.start()
        assert self._page is not None, "Page is None after browser start"
        return self._page

    async def _setup_page(self, page: Page) -> None:
        """
        Apply full antibot stack to a new page:
          1. Extra JS patches (browser-specific)
          2. playwright-stealth with browser-appropriate StealthConfig
        """
        # Для Chromium — полный набор патчей из antibot.py
        # Для Firefox/WebKit — специфичные патчи из stealth.py
        extra = _stealth.get_extra_patches(self._browser_type)
        if extra:
            try:
                await page.add_init_script(extra)
            except Exception as e:
                logger.debug(f"Extra patches ({self._browser_type}) failed: {e}")
        else:
            # Chromium — используем полный набор из antibot.py
            await inject_extra_patches(page)

        if self._stealth_available:
            await _stealth.apply(page, self._browser_type)


# ------------------------------------------------------------------ #
# Module-level helpers                                                 #
# ------------------------------------------------------------------ #

def _schedule_new_page(page: Page, browser_type: str, stealth_available: bool) -> None:
    """
    Called synchronously from context.on("page") — schedule full page setup.
    Применяет JS-патчи и stealth к каждой новой вкладке.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_async_setup_new_page(page, browser_type, stealth_available))
    except Exception:
        pass


async def _async_setup_new_page(page: Page, browser_type: str, stealth_available: bool) -> None:
    """Async: apply patches + stealth to a new page."""
    try:
        extra = _stealth.get_extra_patches(browser_type)
        if extra:
            await page.add_init_script(extra)
        else:
            await inject_extra_patches(page)
        if stealth_available:
            await _stealth.apply(page, browser_type)
    except Exception as e:
        logger.debug(f"New page setup failed (non-critical): {e}")
