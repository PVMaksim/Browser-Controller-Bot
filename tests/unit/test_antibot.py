# tests/unit/test_antibot.py
"""
Tests for antibot utilities:
  - human_delay generates values in range
  - dismiss_cookie_banner tries selectors in order
  - inject_extra_patches calls add_init_script
  - CHROMIUM_ANTIBOT_ARGS contains required flags
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.browser.antibot import (
    CHROMIUM_ANTIBOT_ARGS,
    dismiss_cookie_banner,
    human_delay,
    human_scroll,
    inject_extra_patches,
)


# ------------------------------------------------------------------ #
# human_delay                                                          #
# ------------------------------------------------------------------ #

class TestHumanDelay:

    @pytest.mark.asyncio
    async def test_delay_within_range(self):
        """human_delay должен спать от min_ms до max_ms миллисекунд."""
        slept = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds):
            slept.append(seconds)

        with patch("src.browser.antibot.asyncio.sleep", side_effect=mock_sleep):
            await human_delay(100, 500)

        assert len(slept) == 1
        assert 0.1 <= slept[0] <= 0.5

    @pytest.mark.asyncio
    async def test_default_range(self):
        slept = []
        async def mock_sleep(s): slept.append(s)
        with patch("src.browser.antibot.asyncio.sleep", side_effect=mock_sleep):
            await human_delay()
        assert 0.3 <= slept[0] <= 1.2

    @pytest.mark.asyncio
    async def test_delay_is_random(self):
        """Два вызова должны давать разные значения (с очень высокой вероятностью)."""
        slept = []
        async def mock_sleep(s): slept.append(s)
        with patch("src.browser.antibot.asyncio.sleep", side_effect=mock_sleep):
            await human_delay(0, 10000)
            await human_delay(0, 10000)
        # Статистически: вероятность двух одинаковых значений ≈ 1/10000000
        assert slept[0] != slept[1]


# ------------------------------------------------------------------ #
# human_scroll                                                         #
# ------------------------------------------------------------------ #

class TestHumanScroll:

    @pytest.mark.asyncio
    async def test_scroll_calls_evaluate(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=None)
        with patch("src.browser.antibot.asyncio.sleep"):
            await human_scroll(page, scrolls=2)
        # evaluate вызывается 2 раза (по одному scrollBy на scroll)
        assert page.evaluate.call_count == 2

    @pytest.mark.asyncio
    async def test_scroll_uses_positive_distance(self):
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=None)
        with patch("src.browser.antibot.asyncio.sleep"):
            await human_scroll(page, scrolls=1)
        call_arg = page.evaluate.call_args[0][0]
        # Скролл вниз — положительное смещение
        assert "window.scrollBy" in call_arg
        assert "0, " in call_arg  # (0, Y)


# ------------------------------------------------------------------ #
# inject_extra_patches                                                 #
# ------------------------------------------------------------------ #

class TestInjectExtraPatches:

    @pytest.mark.asyncio
    async def test_calls_add_init_script(self):
        page = AsyncMock()
        page.add_init_script = AsyncMock()
        await inject_extra_patches(page)
        page.add_init_script.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_script_contains_webdriver_patch(self):
        page = AsyncMock()
        captured = []
        async def capture(script): captured.append(script)
        page.add_init_script = capture
        await inject_extra_patches(page)
        assert captured
        assert "webdriver" in captured[0]
        assert "navigator" in captured[0]

    @pytest.mark.asyncio
    async def test_script_contains_chrome_runtime(self):
        page = AsyncMock()
        captured = []
        async def capture(script): captured.append(script)
        page.add_init_script = capture
        await inject_extra_patches(page)
        assert "chrome" in captured[0]
        assert "runtime" in captured[0]

    @pytest.mark.asyncio
    async def test_gracefully_handles_failure(self):
        """inject_extra_patches не должен бросать исключение при ошибке."""
        page = AsyncMock()
        page.add_init_script = AsyncMock(side_effect=Exception("page closed"))
        # Не должно бросать
        await inject_extra_patches(page)


# ------------------------------------------------------------------ #
# dismiss_cookie_banner                                                #
# ------------------------------------------------------------------ #

class TestDismissCookieBanner:

    @pytest.mark.asyncio
    async def test_returns_true_when_banner_found(self):
        page = MagicMock()
        locator = AsyncMock()
        locator.is_visible = AsyncMock(return_value=True)
        locator.click = AsyncMock()
        page.locator = MagicMock(return_value=locator)
        # Мокаем first property
        locator.first = locator

        with patch("src.browser.antibot.asyncio.sleep"):
            result = await dismiss_cookie_banner(page, platform="rutube")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_banner(self):
        page = MagicMock()
        locator = AsyncMock()
        locator.is_visible = AsyncMock(return_value=False)
        locator.first = locator
        page.locator = MagicMock(return_value=locator)

        with patch("src.browser.antibot.asyncio.sleep"):
            result = await dismiss_cookie_banner(page, platform="rutube")

        assert result is False

    @pytest.mark.asyncio
    async def test_works_without_platform(self):
        """Без указания платформы — только общие селекторы."""
        page = MagicMock()
        locator = AsyncMock()
        locator.is_visible = AsyncMock(return_value=False)
        locator.first = locator
        page.locator = MagicMock(return_value=locator)

        with patch("src.browser.antibot.asyncio.sleep"):
            result = await dismiss_cookie_banner(page)

        assert result is False  # Не нашли — тихо вернули False

    @pytest.mark.asyncio
    async def test_handles_selector_exception_gracefully(self):
        """Если locator бросает — переходим к следующему селектору."""
        page = MagicMock()
        locator = AsyncMock()
        locator.is_visible = AsyncMock(side_effect=Exception("timeout"))
        locator.first = locator
        page.locator = MagicMock(return_value=locator)

        with patch("src.browser.antibot.asyncio.sleep"):
            result = await dismiss_cookie_banner(page, platform="youtube")

        assert result is False  # Не упало, вернуло False


# ------------------------------------------------------------------ #
# CHROMIUM_ANTIBOT_ARGS                                                #
# ------------------------------------------------------------------ #

class TestChromiumArgs:

    def test_contains_automation_flag(self):
        assert any("AutomationControlled" in arg for arg in CHROMIUM_ANTIBOT_ARGS)

    def test_contains_disable_infobars(self):
        assert any("infobars" in arg for arg in CHROMIUM_ANTIBOT_ARGS)

    def test_is_list(self):
        assert isinstance(CHROMIUM_ANTIBOT_ARGS, list)

    def test_no_empty_strings(self):
        assert all(arg.strip() for arg in CHROMIUM_ANTIBOT_ARGS)

    def test_has_meaningful_count(self):
        """Ожидаем несколько аргументов, не один."""
        assert len(CHROMIUM_ANTIBOT_ARGS) >= 5


# ------------------------------------------------------------------ #
# User-Agent pool                                                      #
# ------------------------------------------------------------------ #

class TestUserAgentPool:
    from src.browser.antibot import get_random_user_agent, get_user_agent_pool

    def test_get_random_user_agent_returns_string(self):
        from src.browser.antibot import get_random_user_agent
        ua = get_random_user_agent()
        assert isinstance(ua, str)
        assert len(ua) > 40  # Реалистичный UA не может быть коротким

    def test_user_agent_contains_mozilla(self):
        from src.browser.antibot import get_random_user_agent
        ua = get_random_user_agent()
        assert "Mozilla" in ua

    def test_pool_has_multiple_entries(self):
        from src.browser.antibot import get_user_agent_pool
        pool = get_user_agent_pool()
        assert len(pool) >= 5  # У каждого браузера свой пул; chromium имеет 8+ записей

    def test_pool_returns_copy(self):
        from src.browser.antibot import get_user_agent_pool
        pool1 = get_user_agent_pool()
        pool2 = get_user_agent_pool()
        # Мутация копии не влияет на оригинал
        pool1.clear()
        assert len(pool2) > 0

    def test_ua_rotates(self):
        """Разные вызовы должны возвращать разные UA (статистически)."""
        from src.browser.antibot import get_random_user_agent
        results = {get_random_user_agent() for _ in range(50)}
        # За 50 попыток должно встретиться хотя бы 3 разных UA
        assert len(results) >= 3

    def test_all_pool_entries_have_mozilla(self):
        from src.browser.antibot import get_user_agent_pool
        for ua in get_user_agent_pool():
            assert "Mozilla" in ua, f"UA without Mozilla: {ua}"

    def test_pool_includes_different_os(self):
        from src.browser.antibot import get_user_agent_pool
        pool_str = " ".join(get_user_agent_pool())
        assert "Macintosh" in pool_str
        assert "Windows" in pool_str
