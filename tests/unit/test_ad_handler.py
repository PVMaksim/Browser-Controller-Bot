# tests/unit/test_ad_handler.py
"""Unit tests for src/player/ad_handler.py"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.player.ad_handler import is_ad_playing, notify_if_ad_playing


class TestIsAdPlaying:

    @pytest.mark.asyncio
    async def test_returns_true_when_ad_element_found(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=True)
        assert await is_ad_playing(page) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_ad(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=False)
        assert await is_ad_playing(page) is False

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(side_effect=Exception("page closed"))
        assert await is_ad_playing(page) is False


class TestNotifyIfAdPlaying:

    @pytest.mark.asyncio
    async def test_sends_notification_when_ad_detected(self):
        page = AsyncMock()
        bot = AsyncMock()
        with patch("src.player.ad_handler.is_ad_playing", AsyncMock(return_value=True)):
            await notify_if_ad_playing(page, bot, owner_id=99)
        bot.send_message.assert_awaited_once()
        call_args = bot.send_message.call_args
        assert call_args[0][0] == 99
        assert call_args[1]["parse_mode"] == "HTML"
        text = call_args[0][1]
        assert "реклама" in text.lower() or "реклам" in text.lower()

    @pytest.mark.asyncio
    async def test_does_not_send_when_no_ad(self):
        page = AsyncMock()
        bot = AsyncMock()
        with patch("src.player.ad_handler.is_ad_playing", AsyncMock(return_value=False)):
            await notify_if_ad_playing(page, bot, owner_id=99)
        bot.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_silent_on_send_failure(self):
        page = AsyncMock()
        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=Exception("flood"))
        with patch("src.player.ad_handler.is_ad_playing", AsyncMock(return_value=True)):
            await notify_if_ad_playing(page, bot, owner_id=99)  # must not raise
