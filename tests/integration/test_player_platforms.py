# tests/integration/test_player_platforms.py
"""
Integration tests for player platforms.
Проверяем: JS-методы базового класса, интерфейс поиска, контракт SearchResult.
Реальные платформы мокируются — тесты не требуют интернета.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from src.player.platforms.base import BasePlatform, SearchResult


# ------------------------------------------------------------------ #
# Concrete test implementation of BasePlatform                        #
# ------------------------------------------------------------------ #

class _TestPlatform(BasePlatform):
    """Minimal concrete implementation for testing abstract base."""

    async def search(self, page, query: str) -> list[SearchResult]:
        return [SearchResult(
            title=f"Result for {query}",
            url="https://example.com/video",
            duration="1:30:00",
            thumbnail_url=None,
        )]

    async def open_video(self, page, url: str) -> None:
        await page.goto(url)


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    page.goto = AsyncMock()
    return page


@pytest.fixture
def platform():
    return _TestPlatform()


# ------------------------------------------------------------------ #
# SearchResult dataclass                                               #
# ------------------------------------------------------------------ #

class TestSearchResult:

    def test_creation_with_all_fields(self):
        r = SearchResult(
            title="Интерстеллар (2014)",
            url="https://rutube.ru/video/abc",
            duration="2:49:00",
            thumbnail_url="https://i.rutube.ru/thumb.jpg",
        )
        assert r.title == "Интерстеллар (2014)"
        assert r.url == "https://rutube.ru/video/abc"
        assert r.duration == "2:49:00"

    def test_creation_with_optional_nones(self):
        r = SearchResult(title="Test", url="https://x.com", duration=None, thumbnail_url=None)
        assert r.duration is None
        assert r.thumbnail_url is None

    def test_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(SearchResult)


# ------------------------------------------------------------------ #
# Abstract interface contract                                          #
# ------------------------------------------------------------------ #

class TestBasePlatformInterface:

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            BasePlatform()  # type: ignore

    @pytest.mark.asyncio
    async def test_search_returns_list(self, platform, mock_page):
        results = await platform.search(mock_page, "Дюна")
        assert isinstance(results, list)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_returns_search_results(self, platform, mock_page):
        results = await platform.search(mock_page, "test")
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.title
            assert r.url

    @pytest.mark.asyncio
    async def test_open_video_calls_goto(self, platform, mock_page):
        await platform.open_video(mock_page, "https://example.com/video")
        mock_page.goto.assert_awaited_once_with("https://example.com/video")


# ------------------------------------------------------------------ #
# Universal JS controls (HTML5 video API)                              #
# ------------------------------------------------------------------ #

class TestJSControls:

    @pytest.mark.asyncio
    async def test_play_evaluates_js(self, platform, mock_page):
        await platform.play(mock_page)
        mock_page.evaluate.assert_awaited_once()
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "play()" in call_arg

    @pytest.mark.asyncio
    async def test_pause_evaluates_js(self, platform, mock_page):
        await platform.pause(mock_page)
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "pause()" in call_arg

    @pytest.mark.asyncio
    async def test_seek_relative_positive_delta(self, platform, mock_page):
        await platform.seek_relative(mock_page, 30)
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "+= 30" in call_arg or "currentTime" in call_arg

    @pytest.mark.asyncio
    async def test_seek_relative_negative_delta(self, platform, mock_page):
        await platform.seek_relative(mock_page, -30)
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "-30" in call_arg or "currentTime" in call_arg

    @pytest.mark.asyncio
    async def test_seek_absolute(self, platform, mock_page):
        await platform.seek_absolute(mock_page, 120)
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "120" in call_arg

    @pytest.mark.asyncio
    async def test_set_volume_converts_to_float(self, platform, mock_page):
        await platform.set_volume(mock_page, 50)
        call_arg = mock_page.evaluate.call_args[0][0]
        # 50% → 0.5
        assert "0.5" in call_arg

    @pytest.mark.asyncio
    async def test_set_volume_clamps_above_100(self, platform, mock_page):
        await platform.set_volume(mock_page, 150)
        call_arg = mock_page.evaluate.call_args[0][0]
        # Должно быть 1.0 (100%), не 1.5
        assert "1.0" in call_arg

    @pytest.mark.asyncio
    async def test_set_volume_clamps_below_0(self, platform, mock_page):
        await platform.set_volume(mock_page, -10)
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "0.0" in call_arg or "0)" in call_arg

    @pytest.mark.asyncio
    async def test_toggle_mute_evaluates_js(self, platform, mock_page):
        await platform.toggle_mute(mock_page)
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "muted" in call_arg

    @pytest.mark.asyncio
    async def test_get_state_returns_dict(self, platform, mock_page):
        expected = {
            "current_time": 120,
            "duration": 5400,
            "volume": 80,
            "paused": False,
            "muted": False,
        }
        mock_page.evaluate = AsyncMock(return_value=expected)
        state = await platform.get_state(mock_page)
        assert isinstance(state, dict)
        assert "current_time" in state
        assert "paused" in state

    @pytest.mark.asyncio
    async def test_has_video_returns_bool(self, platform, mock_page):
        mock_page.evaluate = AsyncMock(return_value=True)
        result = await platform.has_video(mock_page)
        assert isinstance(result, bool)


# ------------------------------------------------------------------ #
# Platform implementations exist and have correct names               #
# ------------------------------------------------------------------ #

class TestPlatformRegistry:

    def test_rutube_module_exists(self):
        from src.player.platforms import rutube
        # Имя класса: RutubePlatform (строчная t — исторически сложилось)
        assert hasattr(rutube, "RutubePlatform")

    def test_youtube_module_exists(self):
        from src.player.platforms import youtube
        assert hasattr(youtube, "YouTubePlatform")

    def test_vk_module_exists(self):
        from src.player.platforms import vk_video
        assert hasattr(vk_video, "VKVideoPlatform")

    def test_ok_module_exists(self):
        from src.player.platforms import ok_video
        assert hasattr(ok_video, "OKVideoPlatform")

    def test_all_platforms_inherit_base(self):
        from src.player.platforms.rutube import RutubePlatform
        from src.player.platforms.youtube import YouTubePlatform
        from src.player.platforms.vk_video import VKVideoPlatform
        from src.player.platforms.ok_video import OKVideoPlatform
        for cls in (RutubePlatform, YouTubePlatform, VKVideoPlatform, OKVideoPlatform):
            assert issubclass(cls, BasePlatform), f"{cls} must extend BasePlatform"
