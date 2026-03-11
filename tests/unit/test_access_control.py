# tests/unit/test_access_control.py
"""
Tests for Telegram user ID whitelist and access control.
Безопасность — критичный модуль, покрытие 95%+.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.config.settings import Settings
from src.middlewares.access_control import check_access


class TestAccessControl:
    """Tests for Telegram user ID whitelist."""

    @pytest.mark.asyncio
    async def test_owner_is_allowed(self, mock_bot, mock_settings):
        result = await check_access(
            user_id=123456789, bot=mock_bot, settings=mock_settings
        )
        assert result is True
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_stranger_is_blocked(self, mock_bot, mock_settings):
        result = await check_access(
            user_id=999999999, bot=mock_bot, settings=mock_settings
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_blocked_user_triggers_alert_to_owner(self, mock_bot, mock_settings):
        # Владелец должен получить алерт о попытке несанкционированного доступа
        await check_access(user_id=999999999, bot=mock_bot, settings=mock_settings)
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        # Алерт отправляется владельцу (ID 123456789)
        assert call_kwargs[0][0] == 123456789
        # Сообщение содержит информацию о попытке доступа
        alert_text = call_kwargs[0][1]
        assert "Попытка доступа" in alert_text
        # Содержит ID нарушителя
        assert "999999999" in alert_text

    @pytest.mark.asyncio
    async def test_onboarding_mode_blocks_everyone(self, mock_bot, mock_settings):
        # Если ALLOWED_USER_ID не задан — никто не проходит (режим onboarding)
        mock_settings.get.side_effect = lambda key, default=None: None
        result = await check_access(
            user_id=123456789, bot=mock_bot, settings=mock_settings
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_owner_alert_failure_does_not_raise(self, mock_bot, mock_settings):
        # Если отправка алерта упала — не должны бросать исключение в основной код
        mock_bot.send_message.side_effect = Exception("Network error")
        # Не должно бросить исключение
        result = await check_access(
            user_id=999999999, bot=mock_bot, settings=mock_settings
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_allowed_user_id_blocks_all(self, mock_bot, mock_settings):
        # Если ALLOWED_USER_ID содержит невалидное значение — блокируем всех
        mock_settings.get.side_effect = lambda key, default=None: (
            "not_a_number" if key == "ALLOWED_USER_ID" else default
        )
        result = await check_access(
            user_id=123456789, bot=mock_bot, settings=mock_settings
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_zero_user_id_is_blocked(self, mock_bot, mock_settings):
        result = await check_access(
            user_id=0, bot=mock_bot, settings=mock_settings
        )
        assert result is False
