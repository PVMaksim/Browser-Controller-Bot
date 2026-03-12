# src/middlewares/rate_limiter.py
"""
Rate limiting middleware — protection from command flooding.

Бот управляется одним владельцем, но защита от флуда всё равно нужна:
  - Случайный цикл голосовых команд (бесконечный цикл в VoiceCommandMapper)
  - Зависшие скрипты / шорткаты на телефоне
  - Ошибочный двойной tap

Стратегия: скользящее окно (sliding window) по user_id.
Каждый пользователь может отправить не более RATE_LIMIT_MAX_CALLS
сообщений за RATE_LIMIT_WINDOW_SEC секунд.

При превышении — тихий ignore (не отвечаем — не провоцируем ретрай)
плюс WARNING в лог. Опционально: предупреждение пользователю раз в
RATE_LIMIT_NOTIFY_COOLDOWN_SEC.
"""

import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger
from typing import Any, Awaitable, Callable

from src.config.constants import (
    RATE_LIMIT_MAX_CALLS,
    RATE_LIMIT_NOTIFY_COOLDOWN_SEC,
    RATE_LIMIT_WINDOW_SEC,
)


class RateLimiterMiddleware(BaseMiddleware):
    """
    Sliding window rate limiter per user.

    Хранит timestamps последних N запросов в памяти (deque).
    Не требует Redis или любой внешней зависимости.
    Потокобезопасен для asyncio (GIL + deque.appendleft).
    """

    def __init__(
        self,
        max_calls: int = RATE_LIMIT_MAX_CALLS,
        window_sec: float = RATE_LIMIT_WINDOW_SEC,
        notify_cooldown_sec: float = RATE_LIMIT_NOTIFY_COOLDOWN_SEC,
    ) -> None:
        self._max_calls = max_calls
        self._window_sec = window_sec
        self._notify_cooldown_sec = notify_cooldown_sec

        # user_id → deque of timestamps (newest first)
        self._windows: dict[int, deque] = defaultdict(deque)
        # user_id → last time we notified them about rate limit
        self._last_notified: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Check rate limit before passing event to handler.
        Пропускаем не-Message события (callback_query и т.д.) без ограничений.
        """
        user_id = getattr(getattr(event, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return await handler(event, data)

        now = time.monotonic()

        if self._is_rate_limited(user_id, now):
            logger.warning(
                f"Rate limit hit: user_id={user_id}, "
                f"limit={self._max_calls}/{self._window_sec}s"
            )
            await self._maybe_notify(event, user_id, now)
            return  # Отбрасываем событие — не вызываем handler

        return await handler(event, data)

    def _is_rate_limited(self, user_id: int, now: float) -> bool:
        """
        Sliding window check.
        Удаляем устаревшие timestamps, добавляем текущий,
        возвращаем True если превышен лимит.
        """
        window = self._windows[user_id]

        # Удаляем записи старше окна (справа — самые старые)
        while window and now - window[-1] > self._window_sec:
            window.pop()

        if len(window) >= self._max_calls:
            return True

        # Регистрируем текущий запрос
        window.appendleft(now)
        return False

    async def _maybe_notify(self, message: Message, user_id: int, now: float) -> None:
        """
        Send rate limit warning to user — at most once per notify_cooldown_sec.
        Не спамим предупреждениями — отправляем максимум раз в N секунд.
        """
        last = self._last_notified.get(user_id, float('-inf'))
        if now - last < self._notify_cooldown_sec:
            return

        self._last_notified[user_id] = now
        try:
            await message.answer(
                f"⏱ Слишком много команд. "
                f"Подожди {int(self._window_sec)} сек."
            )
        except Exception as e:
            logger.debug(f"Rate limit notify failed: {e}")

    def get_stats(self, user_id: int) -> dict:
        """Return current rate limit stats for a user (for /status or tests)."""
        now = time.monotonic()
        window = self._windows.get(user_id, deque())
        # Считаем только актуальные записи
        active = sum(1 for ts in window if now - ts <= self._window_sec)
        return {
            "user_id": user_id,
            "calls_in_window": active,
            "max_calls": self._max_calls,
            "window_sec": self._window_sec,
        }

    def reset(self, user_id: int | None = None) -> None:
        """Reset rate limit state — all users or specific user (for tests)."""
        if user_id is not None:
            self._windows.pop(user_id, None)
            self._last_notified.pop(user_id, None)
        else:
            self._windows.clear()
            self._last_notified.clear()
