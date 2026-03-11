# tests/unit/test_idle_watcher.py
"""
Tests for browser idle timeout watcher.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.idle_watcher import IdleWatcher


@pytest.fixture
def watcher(mock_settings, mock_bot):
    """IdleWatcher with mocked dependencies."""
    return IdleWatcher(settings=mock_settings, bot=mock_bot, owner_id=123456789)


class TestIdleWatcher:

    def test_reset_updates_last_activity(self, watcher):
        before = watcher._last_activity
        watcher.reset()
        assert watcher._last_activity >= before

    def test_start_creates_background_task(self, watcher):
        watcher.start()
        assert watcher._task is not None
        assert not watcher._task.done()
        watcher.stop()

    def test_start_is_idempotent(self, watcher):
        watcher.start()
        task1 = watcher._task
        watcher.start()  # Второй вызов не должен создавать новую задачу
        assert watcher._task is task1
        watcher.stop()

    def test_stop_cancels_task(self, watcher):
        watcher.start()
        watcher.stop()
        assert watcher._task.cancelled() or watcher._task.done()

    def test_stop_when_not_started_does_not_raise(self, watcher):
        watcher.stop()  # Безопасный вызов без предшествующего start()

    @pytest.mark.asyncio
    async def test_timeout_notification_sent_to_owner(self, watcher, mock_bot):
        """При таймауте владелец получает уведомление."""
        await watcher._on_timeout(timeout_minutes=10)
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args[0][0] == 123456789
        assert "таймаут" in call_args[0][1].lower() or "Браузер закрыт" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_timeout_notification_failure_does_not_raise(self, watcher, mock_bot):
        """Ошибка отправки уведомления не должна бросать исключение."""
        mock_bot.send_message.side_effect = Exception("Network error")
        await watcher._on_timeout(timeout_minutes=10)  # Не должно упасть
