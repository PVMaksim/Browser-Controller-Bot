# src/middlewares/access_control.py
"""
Access control middleware: whitelist by Telegram user ID.
Только один пользователь может управлять ботом.
При несанкционированном доступе — алерт владельцу.
"""

from datetime import datetime

from aiogram import Bot
from loguru import logger

from src.config.settings import Settings


async def check_access(user_id: int, bot: Bot, settings: Settings) -> bool:
    """
    Verify user is authorized to control this bot instance.
    Отправляет алерт владельцу при попытке несанкционированного доступа.

    Returns True if user is the owner, False otherwise.
    """
    allowed_id_raw = settings.get("ALLOWED_USER_ID")

    # Режим onboarding — владелец ещё не зарегистрирован (Этап 5)
    if not allowed_id_raw:
        logger.warning(f"Access attempt from {user_id}, but ALLOWED_USER_ID is not set")
        return False

    try:
        allowed_id = int(allowed_id_raw)
    except (ValueError, TypeError):
        logger.error(f"Invalid ALLOWED_USER_ID value: '{allowed_id_raw}'")
        return False

    if user_id != allowed_id:
        logger.warning(f"Unauthorized access attempt from user_id={user_id}")
        # Алерт владельцу о попытке несанкционированного доступа
        try:
            await bot.send_message(
                allowed_id,
                f"🚨 <b>Попытка доступа</b>\n"
                f"User ID: <code>{user_id}</code>\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="HTML",
            )
        except Exception as alert_error:
            logger.error(f"Failed to send access alert to owner: {alert_error}")
        return False

    return True
