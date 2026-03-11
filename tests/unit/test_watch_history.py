# tests/unit/test_watch_history.py
"""Tests for watch history persistence."""

import pytest
from unittest.mock import patch
from pathlib import Path

from src.player.watch_history import (
    save_position,
    get_position,
    get_recent_history,
    clear_history,
)


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    """Route all history operations to tmp_path."""
    history_file = tmp_path / "watch_history.json"
    monkeypatch.setattr("src.player.watch_history.get_watch_history_file",
                        lambda: history_file)


class TestWatchHistory:

    def test_save_and_get_position(self):
        save_position("https://example.com/1", "Film A", "rutube", 120, 3600)
        pos = get_position("https://example.com/1")
        assert pos is not None
        assert pos["position_sec"] == 120
        assert pos["title"] == "Film A"
        assert pos["platform"] == "rutube"

    def test_get_position_unknown_url(self):
        assert get_position("https://unknown.com") is None

    def test_overwrite_position(self):
        url = "https://example.com/video"
        save_position(url, "T", "rutube", 60, 3600)
        save_position(url, "T", "rutube", 180, 3600)
        pos = get_position(url)
        assert pos["position_sec"] == 180  # Последнее значение

    def test_recent_history_sorted_by_date(self):
        save_position("https://a.com", "A", "rutube", 10, 100)
        save_position("https://b.com", "B", "youtube", 20, 200)
        history = get_recent_history(limit=10)
        # Последнее добавленное — первое в списке
        assert history[0]["title"] == "B"

    def test_recent_history_respects_limit(self):
        for i in range(10):
            save_position(f"https://x.com/{i}", f"Video {i}", "rutube", i * 10, 600)
        history = get_recent_history(limit=3)
        assert len(history) == 3

    def test_clear_history(self):
        save_position("https://x.com/1", "X", "rutube", 1, 100)
        count = clear_history()
        assert count == 1
        assert get_position("https://x.com/1") is None

    def test_history_respects_max_items(self):
        """Старые записи вытесняются когда достигнут лимит."""
        from src.config.constants import DEFAULT_MAX_HISTORY_ITEMS
        # Сохраняем MAX+5 записей
        for i in range(DEFAULT_MAX_HISTORY_ITEMS + 5):
            save_position(f"https://x.com/{i}", f"V{i}", "rutube", i, 600)
        history = get_recent_history(limit=1000)
        assert len(history) <= DEFAULT_MAX_HISTORY_ITEMS
