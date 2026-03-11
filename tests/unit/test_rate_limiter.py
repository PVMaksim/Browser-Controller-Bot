# tests/unit/test_rate_limiter.py
"""
Unit tests for RateLimiterMiddleware.
Проверяем: sliding window, уведомление, reset, stats.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.middlewares.rate_limiter import RateLimiterMiddleware


def _make_message(user_id: int = 42) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


class TestRateLimiter:

    def _limiter(self, max_calls=5, window=10.0, notify_cooldown=60.0):
        return RateLimiterMiddleware(max_calls=max_calls, window_sec=window,
                                     notify_cooldown_sec=notify_cooldown)

    @pytest.mark.asyncio
    async def test_allows_calls_within_limit(self):
        rl = self._limiter(max_calls=3, window=10.0)
        handler = AsyncMock(return_value="ok")
        msg = _make_message()
        for _ in range(3):
            result = await rl(handler, msg, {})
        assert handler.call_count == 3

    @pytest.mark.asyncio
    async def test_blocks_on_exceeded_limit(self):
        rl = self._limiter(max_calls=2, window=10.0, notify_cooldown=9999)
        handler = AsyncMock()
        msg = _make_message()
        await rl(handler, msg, {})
        await rl(handler, msg, {})
        await rl(handler, msg, {})   # 3rd — should be blocked
        assert handler.call_count == 2

    @pytest.mark.asyncio
    async def test_notifies_user_on_rate_limit(self):
        rl = self._limiter(max_calls=1, window=10.0, notify_cooldown=0)
        handler = AsyncMock()
        msg = _make_message()
        await rl(handler, msg, {})   # allowed
        await rl(handler, msg, {})   # blocked → notify
        msg.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notify_cooldown_prevents_spam(self):
        rl = self._limiter(max_calls=1, window=10.0, notify_cooldown=9999)
        handler = AsyncMock()
        msg = _make_message()
        await rl(handler, msg, {})   # allowed
        await rl(handler, msg, {})   # blocked → notify once
        await rl(handler, msg, {})   # blocked → cooldown active, no notify
        assert msg.answer.call_count == 1

    @pytest.mark.asyncio
    async def test_window_slides_over_time(self):
        rl = self._limiter(max_calls=2, window=0.1)
        handler = AsyncMock()
        msg = _make_message()
        await rl(handler, msg, {})
        await rl(handler, msg, {})
        # Wait for window to pass
        await asyncio.sleep(0.15)
        await rl(handler, msg, {})   # should be allowed again
        assert handler.call_count == 3

    @pytest.mark.asyncio
    async def test_different_users_independent_windows(self):
        rl = self._limiter(max_calls=1, window=10.0, notify_cooldown=9999)
        handler = AsyncMock()
        msg1 = _make_message(user_id=1)
        msg2 = _make_message(user_id=2)
        await rl(handler, msg1, {})
        await rl(handler, msg2, {})
        assert handler.call_count == 2  # Both allowed independently

    @pytest.mark.asyncio
    async def test_non_message_events_pass_through(self):
        """Callback queries и другие события не ограничиваются."""
        rl = self._limiter(max_calls=0, window=10.0)  # max_calls=0 = always block Messages
        handler = AsyncMock()
        non_message = MagicMock()  # Not a Message instance
        await rl(handler, non_message, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_without_from_user_passes(self):
        rl = self._limiter(max_calls=1, window=10.0)
        handler = AsyncMock()
        from aiogram.types import Message
        msg = MagicMock(spec=Message)
        msg.from_user = None
        await rl(handler, msg, {})
        handler.assert_awaited_once()

    def test_reset_clears_specific_user(self):
        rl = self._limiter(max_calls=2, window=10.0)
        # Manually populate window
        from collections import deque
        rl._windows[42] = deque([time.monotonic()])
        rl.reset(user_id=42)
        assert 42 not in rl._windows

    def test_reset_clears_all_users(self):
        rl = self._limiter()
        from collections import deque
        rl._windows[1] = deque([time.monotonic()])
        rl._windows[2] = deque([time.monotonic()])
        rl.reset()
        assert len(rl._windows) == 0

    def test_get_stats_returns_dict(self):
        rl = self._limiter()
        stats = rl.get_stats(user_id=99)
        assert isinstance(stats, dict)
        assert stats["user_id"] == 99
        assert "calls_in_window" in stats
        assert stats["max_calls"] == rl._max_calls

    @pytest.mark.asyncio
    async def test_get_stats_counts_active_calls(self):
        rl = self._limiter(max_calls=5, window=10.0)
        handler = AsyncMock()
        msg = _make_message(user_id=7)
        await rl(handler, msg, {})
        await rl(handler, msg, {})
        stats = rl.get_stats(user_id=7)
        assert stats["calls_in_window"] == 2


class TestRateLimitConstants:
    def test_constants_exist(self):
        from src.config.constants import (
            RATE_LIMIT_MAX_CALLS,
            RATE_LIMIT_WINDOW_SEC,
            RATE_LIMIT_NOTIFY_COOLDOWN_SEC,
        )
        assert RATE_LIMIT_MAX_CALLS > 0
        assert RATE_LIMIT_WINDOW_SEC > 0
        assert RATE_LIMIT_NOTIFY_COOLDOWN_SEC > 0

    def test_limit_is_reasonable(self):
        from src.config.constants import RATE_LIMIT_MAX_CALLS, RATE_LIMIT_WINDOW_SEC
        # Не должен блокировать нормальное использование
        assert RATE_LIMIT_MAX_CALLS >= 5
        # Окно не должно быть слишком большим
        assert RATE_LIMIT_WINDOW_SEC <= 60
