# tests/unit/test_watchdog.py
"""
Unit tests for BrowserWatchdog.
Проверяем: probe success/fail, restart flow, max restarts, notifications.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from src.browser.watchdog import BrowserWatchdog


def _make_watchdog(max_restarts=3):
    browser = MagicMock()
    browser.is_running = True
    browser.get_page = MagicMock(return_value=AsyncMock())
    browser.stop = AsyncMock()
    browser.start = AsyncMock()

    settings = MagicMock()
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    return BrowserWatchdog(
        browser=browser,
        settings=settings,
        bot=bot,
        owner_id=12345,
    ), browser, bot


class TestProbe:

    @pytest.mark.asyncio
    async def test_probe_returns_true_on_success(self):
        wd, browser, _ = _make_watchdog()
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=True)
        browser.get_page = MagicMock(return_value=page)
        result = await wd._probe()
        assert result is True

    @pytest.mark.asyncio
    async def test_probe_returns_false_on_timeout(self):
        wd, browser, _ = _make_watchdog()
        page = AsyncMock()
        async def slow_eval(*_): await asyncio.sleep(100)
        page.evaluate = slow_eval
        browser.get_page = MagicMock(return_value=page)

        with patch("src.browser.watchdog.WATCHDOG_PROBE_TIMEOUT_MS", 50):
            result = await wd._probe()
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_returns_false_on_exception(self):
        wd, browser, _ = _make_watchdog()
        page = AsyncMock()
        page.evaluate = AsyncMock(side_effect=RuntimeError("context closed"))
        browser.get_page = MagicMock(return_value=page)
        result = await wd._probe()
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_returns_false_when_no_page(self):
        wd, browser, _ = _make_watchdog()
        browser.get_page = MagicMock(return_value=None)
        result = await wd._probe()
        assert result is False


class TestHandleHang:

    @pytest.mark.asyncio
    async def test_restarts_browser_on_hang(self):
        wd, browser, bot = _make_watchdog()
        with patch("src.browser.watchdog.WATCHDOG_MAX_RESTARTS", 5):
            await wd._handle_hang()
        browser.stop.assert_awaited_once()
        browser.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_increments_restart_count(self):
        wd, browser, _ = _make_watchdog()
        with patch("src.browser.watchdog.WATCHDOG_MAX_RESTARTS", 5):
            await wd._handle_hang()
        assert wd.restart_count == 1

    @pytest.mark.asyncio
    async def test_notifies_owner_after_restart(self):
        wd, browser, bot = _make_watchdog()
        with patch("src.browser.watchdog.WATCHDOG_MAX_RESTARTS", 5):
            await wd._handle_hang()
        bot.send_message.assert_awaited_once()
        msg = bot.send_message.call_args[0][1]
        assert "перезапущен" in msg.lower() or "Перезапущен" in msg

    @pytest.mark.asyncio
    async def test_stops_watchdog_at_max_restarts(self):
        wd, browser, bot = _make_watchdog()
        with patch("src.browser.watchdog.WATCHDOG_MAX_RESTARTS", 2):
            await wd._handle_hang()  # restart 1
            await wd._handle_hang()  # restart 2
            await wd._handle_hang()  # exceeds → stop
        assert not wd.is_running

    @pytest.mark.asyncio
    async def test_notifies_owner_on_max_restarts(self):
        wd, browser, bot = _make_watchdog()
        with patch("src.browser.watchdog.WATCHDOG_MAX_RESTARTS", 1):
            await wd._handle_hang()  # restart 1
            bot.reset_mock()
            await wd._handle_hang()  # exceeds
        bot.send_message.assert_awaited_once()
        msg = bot.send_message.call_args[0][1]
        assert "максимум" in msg.lower() or "максимум" in msg

    @pytest.mark.asyncio
    async def test_handles_restart_failure_gracefully(self):
        wd, browser, bot = _make_watchdog()
        browser.start = AsyncMock(side_effect=RuntimeError("playwright crashed"))
        with patch("src.browser.watchdog.WATCHDOG_MAX_RESTARTS", 5):
            await wd._handle_hang()  # Should not raise
        bot.send_message.assert_awaited_once()


class TestLifecycle:

    @pytest.mark.asyncio
    async def test_starts_and_creates_task(self):
        wd, _, _ = _make_watchdog()
        with patch("src.browser.watchdog.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            wd.start()
            assert wd.is_running
            mock_task.assert_called_once()

    def test_stop_sets_running_false(self):
        wd, _, _ = _make_watchdog()
        wd._running = True
        wd.stop()
        assert not wd.is_running

    def test_double_start_idempotent(self):
        wd, _, _ = _make_watchdog()
        wd._running = True  # Already running
        wd.start()  # Should not create second task
        # Task would be None since we set _running=True manually
        assert wd.is_running

    def test_restart_count_starts_at_zero(self):
        wd, _, _ = _make_watchdog()
        assert wd.restart_count == 0


class TestWatchdogConstants:
    def test_constants_exist(self):
        from src.config.constants import (
            WATCHDOG_CHECK_INTERVAL_SEC,
            WATCHDOG_PROBE_TIMEOUT_MS,
            WATCHDOG_MAX_RESTARTS,
        )
        assert WATCHDOG_CHECK_INTERVAL_SEC > 0
        assert WATCHDOG_PROBE_TIMEOUT_MS > 0
        assert WATCHDOG_MAX_RESTARTS >= 1

    def test_interval_reasonable(self):
        from src.config.constants import WATCHDOG_CHECK_INTERVAL_SEC
        # Не проверяем слишком часто (нагрузка) и не слишком редко (долго висим)
        assert 10 <= WATCHDOG_CHECK_INTERVAL_SEC <= 300

    def test_probe_timeout_shorter_than_interval(self):
        from src.config.constants import WATCHDOG_CHECK_INTERVAL_SEC, WATCHDOG_PROBE_TIMEOUT_MS
        assert WATCHDOG_PROBE_TIMEOUT_MS / 1000 < WATCHDOG_CHECK_INTERVAL_SEC
