# src/handlers/onboarding.py
"""
Onboarding handlers: /register and /start (onboarding mode).
Активны только когда ALLOWED_USER_ID не задан (первый запуск).

Архитектура: onboarding-роутер регистрируется ДО основного роутера команд.
Он перехватывает /start и /register только в режиме onboarding.
В нормальном режиме эти команды обрабатываются основным роутером.
"""

import asyncio

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from src.config.settings import Settings
from src.onboarding.setup_wizard import (
    get_onboarding_welcome_text,
    get_registration_success_text,
    register_owner,
)


def get_onboarding_router(settings: Settings, bot: Bot) -> Router:
    """
    Build onboarding router.
    Хендлеры срабатывают только если бот в режиме onboarding.
    В нормальном режиме роутер регистрируется, но хендлеры сразу возвращают None
    и управление передаётся следующему роутеру.
    """
    r = Router()

    @r.message(Command("start"))
    async def cmd_start_onboarding(message: Message) -> None:
        """
        Show onboarding welcome or pass through to normal /start.
        Если бот не в режиме onboarding — пропускаем (return без ответа).
        """
        if not settings.is_onboarding_mode():
            # Не в режиме onboarding — передаём управление следующему роутеру
            return

        await message.answer(get_onboarding_welcome_text())
        logger.info(
            f"Onboarding /start from user_id={message.from_user.id if message.from_user else '?'}"
        )

    @r.message(Command("register"))
    async def cmd_register(message: Message) -> None:
        """
        Register sender as bot owner.
        Доступна всем пока ALLOWED_USER_ID не задан.
        После регистрации эта команда больше не работает.
        """
        if not message.from_user:
            return

        user_id = message.from_user.id

        # Если уже зарегистрирован — сообщаем и выходим
        if not settings.is_onboarding_mode():
            await message.answer(
                "ℹ️ Владелец уже зарегистрирован.\n"
                "Повторная регистрация невозможна."
            )
            return

        success = await register_owner(
            user_id=user_id,
            settings=settings,
            bot=bot,
        )

        if not success:
            await message.answer("❌ Ошибка регистрации. Попробуй ещё раз.")
            return

        # Отправляем подтверждение и перезапускаем
        await message.answer(get_registration_success_text(user_id))
        logger.info(f"Restarting bot after owner registration: user_id={user_id}")

        # Даём время отправить сообщение перед рестартом
        await asyncio.sleep(1.5)

        # Перезапускаем event loop — бот перечитает конфиг при следующем запуске
        # launchd / KeepAlive=true поднимет процесс автоматически
        asyncio.get_event_loop().stop()

    return r
