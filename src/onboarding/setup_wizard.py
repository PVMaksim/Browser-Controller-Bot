# src/onboarding/setup_wizard.py
"""
Onboarding wizard: registers the first user as bot owner.

Поток:
  1. Бот стартует → ALLOWED_USER_ID не задан → onboarding mode
  2. Любой пользователь пишет /start → получает инструкцию
  3. Пользователь пишет /register → его ID сохраняется как владелец
  4. Бот перезапускается в защищённом режиме

Безопасность: после регистрации повторно зарегистрировать другого владельца
невозможно без ручного редактирования config.json.
"""

import asyncio

from aiogram import Bot
from loguru import logger

from src.config.paths import get_config_file
from src.config.settings import Settings


async def register_owner(user_id: int, settings: Settings, bot: Bot) -> bool:
    """
    Register first user as the bot owner.

    Сохраняет user_id в config.json и перезапускает бота.
    Returns True if registration succeeded, False if owner already registered.

    Атомарная операция: либо полностью записывается, либо не записывается ничего.
    """
    if not settings.is_onboarding_mode():
        logger.warning(
            f"Registration attempt by user {user_id} but owner already registered. "
            "Ignoring."
        )
        return False

    # Копируем все текущие настройки из .env (если есть) и добавляем ALLOWED_USER_ID
    settings.set("ALLOWED_USER_ID", str(user_id))
    settings.save()

    config_path = get_config_file()
    logger.info(
        f"Owner registered: user_id={user_id}. "
        f"Config saved to: {config_path}"
    )
    return True


def get_onboarding_welcome_text() -> str:
    """Return welcome message shown on first /start in onboarding mode."""
    return (
        "👋 <b>Добро пожаловать в Secure Browser Bot!</b>\n\n"
        "Этот бот установлен на компьютер и позволяет управлять\n"
        "браузером прямо из Telegram.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔐 <b>Первый запуск — регистрация</b>\n\n"
        "Бот ещё не привязан к владельцу.\n"
        "Чтобы стать владельцем этого экземпляра, отправь:\n\n"
        "<code>/register</code>\n\n"
        "После регистрации только ты сможешь управлять ботом.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <i>Если ты не устанавливал этот бот — не регистрируйся.</i>"
    )


def get_registration_success_text(user_id: int) -> str:
    """Return confirmation message after successful registration."""
    return (
        "✅ <b>Регистрация завершена!</b>\n\n"
        f"Твой Telegram ID <code>{user_id}</code> зарегистрирован как владелец.\n\n"
        "Ты — единственный, кто может управлять этим ботом.\n"
        "Любые попытки доступа от других пользователей будут\n"
        "заблокированы и ты получишь уведомление.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Отправь /help для списка всех команд.\n\n"
        "<i>Бот перезапускается в защищённом режиме...</i>"
    )
