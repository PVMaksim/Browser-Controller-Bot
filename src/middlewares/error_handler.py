# src/middlewares/error_handler.py
"""
Global error handler: catches all unhandled exceptions and
notifies the owner in Telegram with full traceback.
Каждое необработанное исключение → уведомление владельцу.
"""

import traceback

from aiogram import Bot
from loguru import logger

from src.config.constants import ERROR_TRACEBACK_MAX_LENGTH
from src.config.settings import Settings


async def notify_owner_on_error(
    bot: Bot,
    settings: Settings,
    error: Exception,
    context: str = "",
) -> None:
    """
    Send full error traceback to owner via Telegram.
    Обрезает трейсбек до ERROR_TRACEBACK_MAX_LENGTH символов.
    """
    allowed_id_raw = settings.get("ALLOWED_USER_ID")
    if not allowed_id_raw:
        logger.error("Cannot notify owner: ALLOWED_USER_ID is not set")
        return

    try:
        owner_id = int(allowed_id_raw)
    except (ValueError, TypeError):
        logger.error(f"Cannot notify owner: invalid ALLOWED_USER_ID '{allowed_id_raw}'")
        return

    tb = traceback.format_exc()[:ERROR_TRACEBACK_MAX_LENGTH]
    context_line = f"\n<code>{context}</code>\n\n" if context else "\n\n"
    text = (
        f"🔴 <b>Ошибка бота</b>"
        f"{context_line}"
        f"<pre>{tb}</pre>"
    )

    try:
        await bot.send_message(owner_id, text, parse_mode="HTML")
    except Exception as send_error:
        # Последний рубеж — только лог, чтобы не попасть в рекурсию
        logger.error(f"Failed to send error notification to owner: {send_error}")
