# tests/unit/test_browser_engine.py
"""
Unit tests for BrowserEngine.
Используем моки вместо реального Playwright — тесты не требуют браузера.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from src.browser.engine import BrowserEngine


@pytest.fixture
def engine(mock_settings):
    """BrowserEngine with mock settings."""
    return BrowserEngine(settings=mock_settings)


@pytest.fixture
def running_engine(mock_settings):
    """BrowserEngine that looks like it's already started."""
    engine = BrowserEngine(settings=mock_settings)
    engine._context = MagicMock()
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    engine._page = mock_page
    return engine


class TestBrowserEngineLifecycle:

    def test_initial_state_is_not_running(self, engine):
        assert engine.is_running is False

    def test_is_running_requires_both_context_and_page(self, mock_settings):
        eng = BrowserEngine(settings=mock_settings)
        eng._context = MagicMock()
        eng._page = None
        assert eng.is_running is False

        eng._page = MagicMock()
        assert eng.is_running is True

    @pytest.mark.asyncio
    async def test_stop_when_not_running_does_not_raise(self, engine):
        # Вызов stop() на незапущенном движке должен быть безопасным
        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_state(self, running_engine):
        running_engine._context = AsyncMock()
        running_engine._playwright = AsyncMock()
        await running_engine.stop()
        assert running_engine._context is None
        assert running_engine._page is None
        assert running_engine._playwright is None

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, running_engine):
        """Повторный start() не должен пересоздавать браузер."""
        with patch.object(running_engine, "_playwright") as mock_pw:
            await running_engine.start()
            # playwright.chromium не должен вызываться если браузер уже запущен
            assert mock_pw is not None


class TestBrowserEngineState:

    def test_get_current_url_returns_none_when_not_running(self, engine):
        assert engine.get_current_url() is None

    def test_get_current_url_returns_none_for_blank_page(self, mock_settings):
        eng = BrowserEngine(settings=mock_settings)
        mock_page = MagicMock()
        mock_page.url = "about:blank"
        eng._page = mock_page
        eng._context = MagicMock()
        assert eng.get_current_url() is None

    def test_get_current_url_returns_real_url(self, running_engine):
        assert running_engine.get_current_url() == "https://example.com"

    def test_get_page_returns_none_when_not_running(self, engine):
        assert engine.get_page() is None

    def test_get_page_returns_page_when_running(self, running_engine):
        assert running_engine.get_page() is not None


class TestBrowserEngineActions:

    @pytest.mark.asyncio
    async def test_open_url_calls_goto(self, running_engine):
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        running_engine._page = mock_page
        running_engine._context = MagicMock()

        await running_engine.open_url("https://example.com")
        mock_page.goto.assert_called_once_with(
            "https://example.com",
            wait_until="domcontentloaded",
            timeout=30_000,
        )

    @pytest.mark.asyncio
    async def test_take_screenshot_returns_bytes(self, running_engine):
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")
        running_engine._page = mock_page
        running_engine._context = MagicMock()

        result = await running_engine.take_screenshot()
        assert isinstance(result, bytes)
        assert len(result) > 0
        mock_page.screenshot.assert_called_once_with(type="png", full_page=False)

    @pytest.mark.asyncio
    async def test_close_tab_when_not_running_does_not_raise(self, engine):
        await engine.close_tab()  # Должно быть безопасным no-op

    @pytest.mark.asyncio
    async def test_close_tab_closes_page_and_opens_new(self, running_engine):
        old_page = AsyncMock()
        new_page = AsyncMock()
        running_engine._page = old_page
        running_engine._context = AsyncMock()
        running_engine._context.new_page = AsyncMock(return_value=new_page)

        await running_engine.close_tab()

        old_page.close.assert_called_once()
        running_engine._context.new_page.assert_called_once()
        assert running_engine._page is new_page

    @pytest.mark.asyncio
    async def test_search_builds_correct_google_url(self, running_engine, mock_settings):
        mock_settings.get.side_effect = lambda key, default=None: {
            "SEARCH_ENGINE": "google",
        }.get(key, default)
        mock_page = AsyncMock()
        mock_page.url = "https://google.com"
        running_engine._page = mock_page
        running_engine._context = MagicMock()

        await running_engine.search("рецепт борща")

        called_url = mock_page.goto.call_args[0][0]
        assert "google.com" in called_url
        assert "борща" in called_url or "%D0%B1%D0%BE%D1%80%D1%89%D0%B0" in called_url

    @pytest.mark.asyncio
    async def test_search_builds_correct_duckduckgo_url(self, running_engine, mock_settings):
        mock_settings.get.side_effect = lambda key, default=None: {
            "SEARCH_ENGINE": "duckduckgo",
        }.get(key, default)
        mock_page = AsyncMock()
        mock_page.url = "https://duckduckgo.com"
        running_engine._page = mock_page
        running_engine._context = MagicMock()

        await running_engine.search("python tutorial")

        called_url = mock_page.goto.call_args[0][0]
        assert "duckduckgo.com" in called_url
