# tests/integration/test_browser_actions.py
"""
Integration tests for BrowserEngine actions.
Playwright полностью мокается — тесты проверяют логику движка,
а не реальный браузер (реальный запуск невозможен в CI без дисплея).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from src.browser.engine import BrowserEngine
import src.browser.stealth as _stealth
from src.config.settings import Settings


@pytest.fixture
def mock_settings():
    s = MagicMock(spec=Settings)
    s.get.side_effect = lambda key, default=None: {
        "BROWSER_TYPE": "chromium",
        "BROWSER_HEADLESS": "true",
        "SEARCH_ENGINE": "google",
    }.get(key, default)
    return s


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.url = "https://example.com"
    page.goto = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"PNG_BYTES")
    page.close = AsyncMock()
    return page


@pytest.fixture
def mock_context(mock_page):
    ctx = AsyncMock()
    ctx.pages = [mock_page]
    ctx.new_page = AsyncMock(return_value=mock_page)
    ctx.close = AsyncMock()
    ctx.on = MagicMock()
    return ctx


@pytest.fixture
def mock_playwright(mock_context):
    pw = AsyncMock()
    pw.stop = AsyncMock()
    launcher = AsyncMock()
    launcher.launch_persistent_context = AsyncMock(return_value=mock_context)
    pw.chromium = launcher
    pw.firefox = launcher
    pw.webkit = launcher
    return pw


@pytest.fixture
async def engine(mock_settings, mock_playwright, mock_context):
    """BrowserEngine with fully mocked Playwright internals."""
    with patch("src.browser.engine.async_playwright") as mock_ap, \
         patch("src.browser.engine.get_browser_profile_dir") as mock_dir, \
         patch("src.browser.stealth.is_available", return_value=False):
        mock_ap.return_value.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_dir.return_value = MagicMock()
        mock_dir.return_value.mkdir = MagicMock()

        eng = BrowserEngine(settings=mock_settings)
        eng._playwright = mock_playwright
        eng._context = mock_context
        eng._page = mock_context.pages[0]
        eng._stealth_available = False
        eng._browser_type = "chromium"
        yield eng


class TestBrowserEngineLifecycle:

    @pytest.mark.asyncio
    async def test_is_running_when_context_and_page_set(self, engine):
        assert engine.is_running is True

    @pytest.mark.asyncio
    async def test_is_not_running_after_stop(self, engine):
        await engine.stop()
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_stop_closes_context(self, engine, mock_context):
        await engine.stop()
        mock_context.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_stops_playwright(self, engine, mock_playwright):
        await engine.stop()
        mock_playwright.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self, engine):
        """Повторный start() не должен создавать второй браузер."""
        initial_context = engine._context
        await engine.start()  # already running — should be no-op
        assert engine._context is initial_context


class TestBrowserEngineActions:

    @pytest.mark.asyncio
    async def test_open_url_calls_goto(self, engine, mock_page):
        await engine.open_url("https://youtube.com")
        mock_page.goto.assert_awaited_once_with(
            "https://youtube.com",
            wait_until="domcontentloaded",
            timeout=30_000,
        )

    @pytest.mark.asyncio
    async def test_take_screenshot_returns_bytes(self, engine):
        result = await engine.take_screenshot()
        assert result == b"PNG_BYTES"

    @pytest.mark.asyncio
    async def test_search_builds_google_url(self, engine, mock_page):
        await engine.search("рецепт борща")
        call_url = mock_page.goto.call_args[0][0]
        assert "google.com" in call_url
        assert "%D1%80%D0%B5%D1%86%D0%B5%D0%BF%D1%82" in call_url  # urlencode

    @pytest.mark.asyncio
    async def test_close_tab_opens_new_page(self, engine, mock_context):
        await engine.close_tab()
        mock_context.new_page.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_current_url_returns_url(self, engine):
        url = engine.get_current_url()
        assert url == "https://example.com"

    @pytest.mark.asyncio
    async def test_get_current_url_returns_none_for_blank(self, engine, mock_page):
        mock_page.url = "about:blank"
        assert engine.get_current_url() is None

    @pytest.mark.asyncio
    async def test_get_current_url_returns_none_when_not_running(self, engine):
        engine._page = None
        assert engine.get_current_url() is None


class TestStealthIntegration:

    def test_is_available_returns_bool(self):
        """stealth.is_available() всегда возвращает bool."""
        result = _stealth.is_available()
        assert isinstance(result, bool)

    def test_get_user_agent_returns_string_for_chromium(self):
        ua = _stealth.get_user_agent("chromium")
        assert isinstance(ua, str) and "Mozilla" in ua

    def test_get_extra_patches_returns_none_for_chromium(self):
        assert _stealth.get_extra_patches("chromium") is None

    def test_get_extra_patches_returns_string_for_firefox(self):
        p = _stealth.get_extra_patches("firefox")
        assert isinstance(p, str) and "webdriver" in p

    @pytest.mark.asyncio
    async def test_setup_page_does_not_crash_without_stealth(self, engine):
        """_setup_page работает нормально если stealth недоступен."""
        engine._stealth_available = False
        engine._browser_type = "chromium"
        with patch("src.browser.engine.inject_extra_patches", AsyncMock()), \
             patch("src.browser.stealth.apply", AsyncMock(return_value=False)):
            await engine._setup_page(engine._page)  # должен не упасть

    @pytest.mark.asyncio
    async def test_setup_page_calls_stealth_when_available(self, engine, mock_page):
        """_setup_page вызывает stealth.apply если stealth доступен."""
        engine._stealth_available = True
        engine._browser_type = "chromium"
        mock_apply = AsyncMock(return_value=True)
        with patch("src.browser.engine.inject_extra_patches", AsyncMock()), \
             patch("src.browser.stealth.apply", mock_apply):
            await engine._setup_page(mock_page)
        mock_apply.assert_awaited_once_with(mock_page, "chromium")


class TestSearchEngine:

    @pytest.mark.asyncio
    async def test_duckduckgo_search(self, engine, mock_settings, mock_page):
        mock_settings.get.side_effect = lambda key, default=None: {
            "BROWSER_TYPE": "chromium",
            "BROWSER_HEADLESS": "true",
            "SEARCH_ENGINE": "duckduckgo",
        }.get(key, default)
        await engine.search("test query")
        call_url = mock_page.goto.call_args[0][0]
        assert "duckduckgo.com" in call_url

    @pytest.mark.asyncio
    async def test_unknown_engine_falls_back_to_google(self, engine, mock_settings, mock_page):
        mock_settings.get.side_effect = lambda key, default=None: {
            "SEARCH_ENGINE": "bing",
        }.get(key, default)
        await engine.search("test")
        call_url = mock_page.goto.call_args[0][0]
        assert "google.com" in call_url
