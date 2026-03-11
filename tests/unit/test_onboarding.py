# tests/unit/test_onboarding.py
"""Tests for onboarding wizard: registration flow."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.onboarding.setup_wizard import (
    register_owner,
    get_onboarding_welcome_text,
    get_registration_success_text,
)
from src.config.settings import Settings


@pytest.fixture
def onboarding_settings(tmp_path, monkeypatch):
    """Fresh empty Settings in onboarding mode."""
    cf = tmp_path / "config.json"
    cf.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("src.config.settings.get_config_file", lambda: cf)
    monkeypatch.setattr("src.onboarding.setup_wizard.get_config_file", lambda: cf)
    return Settings(), cf


@pytest.fixture
def registered_settings(tmp_path, monkeypatch):
    """Settings where owner is already registered."""
    cf = tmp_path / "config.json"
    cf.write_text(json.dumps({"ALLOWED_USER_ID": "111"}), encoding="utf-8")
    monkeypatch.setattr("src.config.settings.get_config_file", lambda: cf)
    return Settings(), cf


class TestRegisterOwner:

    @pytest.mark.asyncio
    async def test_registers_first_user(self, onboarding_settings):
        settings, cf = onboarding_settings
        mock_bot = AsyncMock()
        result = await register_owner(user_id=42, settings=settings, bot=mock_bot)
        assert result is True

    @pytest.mark.asyncio
    async def test_persists_user_id(self, onboarding_settings):
        settings, cf = onboarding_settings
        mock_bot = AsyncMock()
        await register_owner(user_id=123456789, settings=settings, bot=mock_bot)
        saved = json.loads(cf.read_text())
        assert saved["ALLOWED_USER_ID"] == "123456789"

    @pytest.mark.asyncio
    async def test_returns_false_if_already_registered(self, registered_settings):
        settings, _ = registered_settings
        mock_bot = AsyncMock()
        result = await register_owner(user_id=999, settings=settings, bot=mock_bot)
        assert result is False

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_owner(self, registered_settings):
        settings, cf = registered_settings
        mock_bot = AsyncMock()
        await register_owner(user_id=999, settings=settings, bot=mock_bot)
        saved = json.loads(cf.read_text())
        # Оригинальный владелец не должен быть перезаписан
        assert saved["ALLOWED_USER_ID"] == "111"

    @pytest.mark.asyncio
    async def test_bot_not_called_on_duplicate(self, registered_settings):
        """register_owner не должен вызывать bot при дублировании."""
        settings, _ = registered_settings
        mock_bot = AsyncMock()
        await register_owner(user_id=999, settings=settings, bot=mock_bot)
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_leaves_onboarding_mode_after_registration(self, onboarding_settings):
        settings, _ = onboarding_settings
        mock_bot = AsyncMock()
        assert settings.is_onboarding_mode() is True
        await register_owner(user_id=555, settings=settings, bot=mock_bot)
        settings.reload()
        assert settings.is_onboarding_mode() is False


class TestOnboardingTexts:

    def test_welcome_text_contains_register_command(self):
        text = get_onboarding_welcome_text()
        assert "/register" in text

    def test_welcome_text_is_non_empty(self):
        text = get_onboarding_welcome_text()
        assert len(text) > 50

    def test_success_text_contains_user_id(self):
        text = get_registration_success_text(user_id=123456789)
        assert "123456789" in text

    def test_success_text_mentions_help(self):
        text = get_registration_success_text(user_id=1)
        assert "/help" in text
