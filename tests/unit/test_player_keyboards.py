# tests/unit/test_player_keyboards.py
"""Tests for player inline keyboard builders."""

import pytest
from src.player.keyboards import (
    build_player_keyboard,
    build_search_results_keyboard,
    build_resume_keyboard,
)
from src.player.platforms.base import SearchResult


class TestPlayerKeyboard:

    def test_has_play_and_pause_buttons(self):
        kb = build_player_keyboard("rutube")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "player:play" in all_cbs
        assert "player:pause" in all_cbs

    def test_has_seek_buttons(self):
        kb = build_player_keyboard("rutube")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "player:seek:-30" in all_cbs
        assert "player:seek:+30" in all_cbs
        assert "player:seek:-300" in all_cbs
        assert "player:seek:+300" in all_cbs

    def test_has_volume_and_mute(self):
        kb = build_player_keyboard("youtube")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "player:vol:-20" in all_cbs
        assert "player:vol:+20" in all_cbs
        assert "player:mute" in all_cbs

    def test_has_close_button(self):
        kb = build_player_keyboard("vk")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "player:close" in all_cbs


class TestSearchResultsKeyboard:

    def _make_results(self, n: int) -> list[SearchResult]:
        return [
            SearchResult(title=f"Фильм {i}", url=f"https://rutube.ru/{i}",
                         duration="2:00:00", thumbnail_url=None)
            for i in range(1, n + 1)
        ]

    def test_shows_max_5_results(self):
        kb = build_search_results_keyboard(self._make_results(10))
        assert len(kb.inline_keyboard) == 5

    def test_shows_all_when_fewer_than_5(self):
        kb = build_search_results_keyboard(self._make_results(3))
        assert len(kb.inline_keyboard) == 3

    def test_empty_list_gives_empty_keyboard(self):
        kb = build_search_results_keyboard([])
        assert len(kb.inline_keyboard) == 0

    def test_long_title_is_truncated(self):
        long_title = "Очень длинное название фильма которое точно не уместится в кнопку целиком"
        results = [SearchResult(title=long_title, url="https://x.com/1",
                                duration=None, thumbnail_url=None)]
        kb = build_search_results_keyboard(results)
        btn_text = kb.inline_keyboard[0][0].text
        assert len(btn_text) <= 70

    def test_callback_data_uses_index(self):
        kb = build_search_results_keyboard(self._make_results(3))
        callbacks = [kb.inline_keyboard[i][0].callback_data for i in range(3)]
        assert callbacks == ["player:open:1", "player:open:2", "player:open:3"]

    def test_duration_shown_in_button(self):
        results = [SearchResult(title="Фильм", url="https://x.com",
                                duration="2:49:00", thumbnail_url=None)]
        kb = build_search_results_keyboard(results)
        btn_text = kb.inline_keyboard[0][0].text
        assert "2:49:00" in btn_text


class TestResumeKeyboard:

    def test_has_continue_and_restart(self):
        kb = build_resume_keyboard("47:23")
        all_cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert "player:resume" in all_cbs
        assert "player:restart" in all_cbs

    def test_position_shown_in_continue_button(self):
        kb = build_resume_keyboard("1:23:45")
        all_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("1:23:45" in t for t in all_texts)
