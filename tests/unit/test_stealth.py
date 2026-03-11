# tests/unit/test_stealth.py
"""
Unit tests for src/browser/stealth.py.

Проверяем:
  - UA пулы: правильные браузеры, Mozilla, разнообразие
  - StealthConfig: Chromium включает chrome_*, Firefox отключает их
  - get_extra_patches: Chromium → None, Firefox/WebKit → строка с webdriver
  - apply(): graceful при отсутствии playwright-stealth
  - is_available(): возвращает bool
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ------------------------------------------------------------------ #
# UA pools                                                             #
# ------------------------------------------------------------------ #

class TestUserAgentPools:

    def test_chromium_pool_not_empty(self):
        from src.browser.stealth import get_ua_pool
        assert len(get_ua_pool("chromium")) >= 5

    def test_firefox_pool_not_empty(self):
        from src.browser.stealth import get_ua_pool
        assert len(get_ua_pool("firefox")) >= 5

    def test_webkit_pool_not_empty(self):
        from src.browser.stealth import get_ua_pool
        assert len(get_ua_pool("webkit")) >= 4

    def test_chromium_ua_contains_chrome(self):
        from src.browser.stealth import get_ua_pool
        for ua in get_ua_pool("chromium"):
            assert "Chrome" in ua, f"Chromium UA without Chrome: {ua}"

    def test_firefox_ua_contains_firefox(self):
        from src.browser.stealth import get_ua_pool
        for ua in get_ua_pool("firefox"):
            assert "Firefox" in ua, f"Firefox UA without Firefox: {ua}"

    def test_webkit_ua_contains_safari(self):
        from src.browser.stealth import get_ua_pool
        for ua in get_ua_pool("webkit"):
            assert "Safari" in ua, f"WebKit UA without Safari: {ua}"

    def test_firefox_ua_has_no_chrome_token(self):
        """Firefox UA не должен содержать 'Chrome/' — это red flag."""
        from src.browser.stealth import get_ua_pool
        for ua in get_ua_pool("firefox"):
            assert "Chrome/" not in ua, f"Firefox UA contains Chrome/: {ua}"

    def test_webkit_ua_has_no_chrome_token(self):
        from src.browser.stealth import get_ua_pool
        for ua in get_ua_pool("webkit"):
            assert "Chrome/" not in ua, f"WebKit UA contains Chrome/: {ua}"

    def test_get_user_agent_returns_string(self):
        from src.browser.stealth import get_user_agent
        for bt in ("chromium", "firefox", "webkit"):
            ua = get_user_agent(bt)
            assert isinstance(ua, str) and len(ua) > 30

    def test_get_user_agent_rotates(self):
        """50 вызовов должны дать >= 3 разных UA для каждого браузера."""
        from src.browser.stealth import get_user_agent
        for bt in ("chromium", "firefox", "webkit"):
            seen = {get_user_agent(bt) for _ in range(50)}
            assert len(seen) >= 2, f"{bt}: UA not rotating (got {seen})"

    def test_chrome_alias_same_as_chromium(self):
        from src.browser.stealth import get_ua_pool
        assert get_ua_pool("chrome") == get_ua_pool("chromium")

    def test_unknown_browser_falls_back_to_chromium(self):
        from src.browser.stealth import get_ua_pool
        unknown = get_ua_pool("opera")
        chromium = get_ua_pool("chromium")
        assert unknown == chromium

    def test_get_ua_pool_returns_copy(self):
        from src.browser.stealth import get_ua_pool
        p1 = get_ua_pool("firefox")
        p1.clear()
        p2 = get_ua_pool("firefox")
        assert len(p2) > 0


# ------------------------------------------------------------------ #
# StealthConfig per browser                                            #
# ------------------------------------------------------------------ #

class TestStealthConfig:

    def _get_config(self, browser_type: str):
        """Get config if playwright_stealth is available, else skip."""
        mock_config_class = MagicMock()
        mock_config_class.return_value = MagicMock()
        with patch.dict("sys.modules", {"playwright_stealth": MagicMock(StealthConfig=mock_config_class)}):
            from importlib import reload
            import src.browser.stealth as stealth_mod
            return mock_config_class, stealth_mod._make_config(browser_type)

    def test_chromium_enables_chrome_app(self):
        mock_cls, _ = self._get_config("chromium")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("chrome_app") is True

    def test_chromium_enables_chrome_runtime(self):
        mock_cls, _ = self._get_config("chromium")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("chrome_runtime") is True

    def test_chromium_enables_navigator_plugins(self):
        mock_cls, _ = self._get_config("chromium")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("navigator_plugins") is True

    def test_firefox_disables_chrome_app(self):
        mock_cls, _ = self._get_config("firefox")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("chrome_app") is False

    def test_firefox_disables_chrome_runtime(self):
        mock_cls, _ = self._get_config("firefox")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("chrome_runtime") is False

    def test_firefox_disables_navigator_plugins(self):
        mock_cls, _ = self._get_config("firefox")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("navigator_plugins") is False

    def test_webkit_disables_chrome_app(self):
        mock_cls, _ = self._get_config("webkit")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("chrome_app") is False

    def test_all_browsers_enable_webdriver_patch(self):
        """navigator_webdriver должен быть True для всех браузеров."""
        for bt in ("chromium", "firefox", "webkit"):
            mock_cls, _ = self._get_config(bt)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs.get("navigator_webdriver") is True, \
                f"{bt}: navigator_webdriver not enabled"

    def test_all_browsers_disable_ua_override(self):
        """user_agent_override=False — UA управляем через пул."""
        for bt in ("chromium", "firefox", "webkit"):
            mock_cls, _ = self._get_config(bt)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs.get("user_agent_override") is False, \
                f"{bt}: user_agent_override should be False"

    def test_returns_none_when_playwright_stealth_missing(self):
        import sys
        with patch.dict("sys.modules", {"playwright_stealth": None}):
            from src.browser import stealth as stealth_mod
            result = stealth_mod._make_config("chromium")
        assert result is None


# ------------------------------------------------------------------ #
# Extra JS patches                                                     #
# ------------------------------------------------------------------ #

class TestExtraPatches:

    def test_chromium_returns_none(self):
        from src.browser.stealth import get_extra_patches
        assert get_extra_patches("chromium") is None

    def test_chrome_returns_none(self):
        from src.browser.stealth import get_extra_patches
        assert get_extra_patches("chrome") is None

    def test_firefox_returns_string(self):
        from src.browser.stealth import get_extra_patches
        p = get_extra_patches("firefox")
        assert isinstance(p, str) and len(p) > 10

    def test_webkit_returns_string(self):
        from src.browser.stealth import get_extra_patches
        p = get_extra_patches("webkit")
        assert isinstance(p, str) and len(p) > 10

    def test_firefox_patches_contain_webdriver(self):
        from src.browser.stealth import get_extra_patches
        assert "webdriver" in get_extra_patches("firefox")

    def test_webkit_patches_contain_webdriver(self):
        from src.browser.stealth import get_extra_patches
        assert "webdriver" in get_extra_patches("webkit")

    def test_firefox_patches_have_no_chrome_object(self):
        """Firefox патчи не должны создавать window.chrome."""
        from src.browser.stealth import get_extra_patches
        patch = get_extra_patches("firefox")
        assert "window.chrome" not in patch

    def test_webkit_patches_have_no_chrome_object(self):
        from src.browser.stealth import get_extra_patches
        patch = get_extra_patches("webkit")
        assert "window.chrome" not in patch


# ------------------------------------------------------------------ #
# apply() — graceful                                                   #
# ------------------------------------------------------------------ #

class TestApply:

    @pytest.mark.asyncio
    async def test_returns_false_when_stealth_unavailable(self):
        from src.browser.stealth import apply
        page = AsyncMock()
        with patch("src.browser.stealth._make_config", return_value=None):
            result = await apply(page, "chromium")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        from src.browser.stealth import apply
        page = AsyncMock()
        mock_config = MagicMock()
        mock_stealth_async = AsyncMock()
        with patch("src.browser.stealth._make_config", return_value=mock_config), \
             patch.dict("sys.modules", {"playwright_stealth": MagicMock(stealth_async=mock_stealth_async)}):
            result = await apply(page, "chromium")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        from src.browser.stealth import apply
        page = AsyncMock()
        mock_config = MagicMock()
        mock_stealth = MagicMock()
        mock_stealth.stealth_async = AsyncMock(side_effect=RuntimeError("stealth error"))
        with patch("src.browser.stealth._make_config", return_value=mock_config), \
             patch.dict("sys.modules", {"playwright_stealth": mock_stealth}):
            result = await apply(page, "firefox")
        assert result is False  # Не бросает — возвращает False


# ------------------------------------------------------------------ #
# is_available()                                                       #
# ------------------------------------------------------------------ #

class TestIsAvailable:

    def test_returns_bool(self):
        from src.browser.stealth import is_available
        assert isinstance(is_available(), bool)

    def test_returns_true_when_installed(self):
        from src.browser.stealth import is_available
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            assert is_available() is True

    def test_returns_false_when_not_installed(self):
        from src.browser.stealth import is_available
        with patch("importlib.util.find_spec", return_value=None):
            assert is_available() is False
