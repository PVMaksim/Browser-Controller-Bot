# tests/unit/test_error_handler.py
"""Unit tests for src/middlewares/error_handler.py"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.middlewares.error_handler import notify_owner_on_error
from src.config.settings import Settings


def _settings(user_id="12345"):
    s = MagicMock(spec=Settings)
    s.get.side_effect = lambda key, default=None: {
        "ALLOWED_USER_ID": user_id
    }.get(key, default)
    return s


class TestNotifyOwnerOnError:

    @pytest.mark.asyncio
    async def test_sends_message_to_owner(self):
        bot = AsyncMock()
        await notify_owner_on_error(bot, _settings("42"), ValueError("boom"))
        bot.send_message.assert_awaited_once()
        call_id = bot.send_message.call_args[0][0]
        assert call_id == 42

    @pytest.mark.asyncio
    async def test_message_contains_error_marker(self):
        bot = AsyncMock()
        await notify_owner_on_error(bot, _settings(), RuntimeError("test err"))
        text = bot.send_message.call_args[0][1]
        assert "Ошибка" in text

    @pytest.mark.asyncio
    async def test_includes_context_when_provided(self):
        bot = AsyncMock()
        await notify_owner_on_error(bot, _settings(), Exception("x"), context="handler: /open")
        text = bot.send_message.call_args[0][1]
        assert "handler: /open" in text

    @pytest.mark.asyncio
    async def test_skips_context_when_empty(self):
        bot = AsyncMock()
        await notify_owner_on_error(bot, _settings(), Exception("x"), context="")
        bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_nothing_without_owner_id(self):
        bot = AsyncMock()
        await notify_owner_on_error(bot, _settings(user_id=None), Exception("x"))
        bot.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_nothing_with_invalid_owner_id(self):
        bot = AsyncMock()
        await notify_owner_on_error(bot, _settings(user_id="not-a-number"), Exception("x"))
        bot.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_silent_on_send_failure(self):
        """If bot.send_message raises, the function should not propagate."""
        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=Exception("network error"))
        # Should not raise
        await notify_owner_on_error(bot, _settings(), Exception("original"))
