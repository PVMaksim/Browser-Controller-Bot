# tests/unit/test_search_retry.py
"""
Tests for PlayerController.search() retry logic.
Проверяем: повтор при 0 результатах, повтор при исключении,
ограничение числа попыток, логирование, успех на N-й попытке.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.player.controller import PlayerController
from src.player.platforms.base import SearchResult
from src.config.settings import Settings


# ─── Fixtures ─────────────────────────────────────────────────────

def _make_settings(retry_count=2, retry_delay=0.0, limit=5):
    """Settings mock with retry and search parameters."""
    s = MagicMock(spec=Settings)
    s.get.side_effect = lambda key, default=None: {
        "DEFAULT_MEDIA_PLATFORM": "rutube",
        "SEARCH_RESULTS_LIMIT": str(limit),
        "POSITION_SAVE_INTERVAL_SEC": "30",
    }.get(key, default)
    return s


def _make_result(title="Test Video") -> SearchResult:
    return SearchResult(
        title=title,
        url="https://rutube.ru/video/abc",
        duration="1:30:00",
        thumbnail_url=None,
    )


@pytest.fixture
def controller():
    settings = _make_settings()
    browser = MagicMock()
    browser.is_running = True
    browser.get_page = MagicMock(return_value=AsyncMock())
    browser.start = AsyncMock()
    bot = AsyncMock()
    return PlayerController(settings=settings, browser=browser, bot=bot, owner_id=123)


# ─── Retry on empty results ───────────────────────────────────────

class TestRetryOnEmptyResults:

    @pytest.mark.asyncio
    async def test_returns_results_on_first_success(self, controller):
        results = [_make_result("Интерстеллар")]
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(return_value=results)

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            found = await controller.search("Интерстеллар", platform="rutube")

        assert len(found) == 1
        assert found[0].title == "Интерстеллар"
        mock_platform.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_when_zero_results_then_succeeds(self, controller):
        """
        Первые два вызова возвращают [], третий — результаты.
        Ожидаем ровно 3 вызова и 2 паузы.
        """
        results = [_make_result()]
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(side_effect=[[], [], results])
        sleep_calls = []

        async def mock_sleep(s): sleep_calls.append(s)

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", side_effect=mock_sleep):
            found = await controller.search("test", platform="rutube")

        assert len(found) == 1
        assert mock_platform.search.call_count == 3
        assert len(sleep_calls) == 2  # Пауза перед попыткой 2 и перед попыткой 3

    @pytest.mark.asyncio
    async def test_returns_empty_after_all_retries_exhausted(self, controller):
        """Все 3 попытки вернули [] — возвращаем пустой список, не бросаем."""
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(return_value=[])

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            found = await controller.search("ничего нет", platform="rutube")

        assert found == []
        # 1 первая попытка + SEARCH_RETRY_COUNT (2) = 3 вызова
        assert mock_platform.search.call_count == 3

    @pytest.mark.asyncio
    async def test_state_updated_with_empty_results(self, controller):
        """state.search_results обновляется даже при пустом результате."""
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(return_value=[])

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            await controller.search("test")

        assert controller.state.search_results == []


# ─── Retry on exception ───────────────────────────────────────────

class TestRetryOnException:

    @pytest.mark.asyncio
    async def test_retries_after_exception(self, controller):
        """Первый вызов бросает исключение, второй — возвращает результаты."""
        results = [_make_result()]
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(side_effect=[RuntimeError("timeout"), results])

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            found = await controller.search("test")

        assert len(found) == 1
        assert mock_platform.search.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_last_exception_when_all_fail(self, controller):
        """Все попытки упали с исключением — пробрасываем последнее."""
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(
            side_effect=RuntimeError("network error")
        )

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="network error"):
                await controller.search("test")

    @pytest.mark.asyncio
    async def test_no_retry_needed_if_first_call_succeeds(self, controller):
        results = [_make_result("Дюна")]
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(return_value=results)
        sleep_mock = AsyncMock()

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", sleep_mock):
            await controller.search("Дюна")

        sleep_mock.assert_not_awaited()  # Нет паузы если всё хорошо сразу


# ─── Result limits ────────────────────────────────────────────────

class TestResultLimit:

    @pytest.mark.asyncio
    async def test_results_capped_at_limit(self, controller):
        """Результаты обрезаются до SEARCH_RESULTS_LIMIT."""
        many = [_make_result(f"Video {i}") for i in range(10)]
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(return_value=many)

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            found = await controller.search("test")

        assert len(found) <= 5  # DEFAULT limit = 5 in fixture

    @pytest.mark.asyncio
    async def test_state_search_results_saved(self, controller):
        results = [_make_result("Movie")]
        mock_platform = AsyncMock()
        mock_platform.search = AsyncMock(return_value=results)

        with patch.object(controller, "_get_platform", return_value=mock_platform), \
             patch("src.player.controller._asyncio_retry.sleep", new_callable=AsyncMock):
            await controller.search("Movie", platform="youtube")

        assert controller.state.search_results == results
        assert controller.state.platform == "youtube"


# ─── Constants sanity ─────────────────────────────────────────────

class TestRetryConstants:

    def test_retry_count_positive(self):
        from src.config.constants import SEARCH_RETRY_COUNT
        assert SEARCH_RETRY_COUNT >= 1

    def test_retry_delay_positive(self):
        from src.config.constants import SEARCH_RETRY_DELAY_SEC
        assert SEARCH_RETRY_DELAY_SEC > 0

    def test_retry_count_reasonable(self):
        """Не делаем слишком много попыток — не хотим блокировок."""
        from src.config.constants import SEARCH_RETRY_COUNT
        assert SEARCH_RETRY_COUNT <= 5
