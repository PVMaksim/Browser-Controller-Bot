# tests/unit/test_watchlist.py
"""Tests for watch-later list."""

import pytest

from src.player.watchlist import (
    add_to_watchlist,
    clear_watchlist,
    get_watchlist,
    is_in_watchlist,
    remove_from_watchlist,
)


@pytest.fixture(autouse=True)
def isolated_watchlist(tmp_path, monkeypatch):
    """Route all watchlist operations to tmp_path."""
    wl_file = tmp_path / "watchlist.json"
    monkeypatch.setattr("src.player.watchlist.get_watchlist_file", lambda: wl_file)


class TestWatchlist:

    def test_add_and_check(self):
        added = add_to_watchlist("https://rutube.ru/1", "Фильм", "rutube", "2:00:00")
        assert added is True
        assert is_in_watchlist("https://rutube.ru/1") is True

    def test_no_duplicates(self):
        add_to_watchlist("https://rutube.ru/1", "Фильм", "rutube")
        result = add_to_watchlist("https://rutube.ru/1", "Фильм", "rutube")
        assert result is False
        assert len(get_watchlist()) == 1

    def test_remove_existing(self):
        add_to_watchlist("https://rutube.ru/1", "Фильм", "rutube")
        removed = remove_from_watchlist("https://rutube.ru/1")
        assert removed is True
        assert is_in_watchlist("https://rutube.ru/1") is False

    def test_remove_nonexistent(self):
        assert remove_from_watchlist("https://no-such.url") is False

    def test_get_watchlist_sorted_newest_first(self):
        add_to_watchlist("https://a.com", "A", "rutube")
        add_to_watchlist("https://b.com", "B", "youtube")
        items = get_watchlist()
        assert items[0]["title"] == "B"

    def test_clear_watchlist(self):
        add_to_watchlist("https://a.com", "A", "rutube")
        add_to_watchlist("https://b.com", "B", "youtube")
        count = clear_watchlist()
        assert count == 2
        assert get_watchlist() == []

    def test_unknown_url_not_in_watchlist(self):
        assert is_in_watchlist("https://totally-unknown.com") is False

    def test_watchlist_stores_duration(self):
        add_to_watchlist("https://x.com", "T", "ok", duration="1:30:00")
        items = get_watchlist()
        assert items[0]["duration"] == "1:30:00"
