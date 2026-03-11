# src/utils/sanitize.py
"""
Text sanitization helpers for Telegram message limits.
"""

from src.config.constants import TELEGRAM_MAX_CAPTION_LENGTH


def sanitize_caption(text: str) -> str:
    """
    Truncate text to Telegram photo caption limit.
    Telegram обрезает подписи к фото после 1024 символов — делаем это сами с многоточием.
    """
    if len(text) <= TELEGRAM_MAX_CAPTION_LENGTH:
        return text
    return text[: TELEGRAM_MAX_CAPTION_LENGTH - 3] + "..."
