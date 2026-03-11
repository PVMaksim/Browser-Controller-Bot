# tests/conftest.py
"""
Shared pytest fixtures for all tests.
Мок-объекты без реальных зависимостей (.env, Telegram API, БД).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.config.settings import Settings


@pytest.fixture
def mock_bot():
    """Mock aiogram Bot instance."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=True)
    return bot


@pytest.fixture
def mock_settings():
    """Settings with test values — no real .env needed."""
    settings = MagicMock(spec=Settings)
    settings.get.side_effect = lambda key, default=None: {
        "ALLOWED_USER_ID": "123456789",
        "BROWSER_TYPE": "chromium",
        "BROWSER_HEADLESS": "false",
        "WHISPER_MODEL": "base",
        "LOG_LEVEL": "INFO",
        "SEARCH_ENGINE": "google",
        "IDLE_TIMEOUT_MINUTES": "10",
        "STOP_CONFIRM_TIMEOUT_SECONDS": "30",
    }.get(key, default)
    return settings


@pytest.fixture
def mock_message(mock_bot):
    """Mock Telegram Message object."""
    message = AsyncMock()
    message.bot = mock_bot
    message.from_user = MagicMock()
    message.from_user.id = 123456789
    message.answer = AsyncMock()
    message.text = ""
    return message


# ------------------------------------------------------------------ #
# Integration test helpers                                             #
# ------------------------------------------------------------------ #

def pytest_configure(config):
    """Register custom markers (also declared in pytest.ini)."""
    config.addinivalue_line(
        "markers", "integration: marks tests requiring real browser/network"
    )
    config.addinivalue_line(
        "markers", "slow: marks slow tests (deselect with -m 'not slow')"
    )


@pytest.fixture
def mock_browser():
    """Mock BrowserEngine — no real Playwright needed."""
    from src.browser.engine import BrowserEngine
    from src.config.settings import Settings

    browser = MagicMock(spec=BrowserEngine)
    browser.is_running = True
    browser.get_current_url = MagicMock(return_value="https://example.com")
    browser.open_url = AsyncMock()
    browser.take_screenshot = AsyncMock(return_value=b"\x89PNG")
    browser.search = AsyncMock()
    browser.close_tab = AsyncMock()
    browser.start = AsyncMock()
    browser.stop = AsyncMock()
    browser.get_page = MagicMock(return_value=AsyncMock())
    return browser


@pytest.fixture
def mock_page():
    """Mock Playwright Page."""
    page = AsyncMock()
    page.url = "https://example.com"
    page.goto = AsyncMock()
    page.evaluate = AsyncMock(return_value=True)
    page.screenshot = AsyncMock(return_value=b"\x89PNG")
    page.locator = MagicMock(return_value=AsyncMock())
    return page
