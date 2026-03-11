# tests/unit/test_player_state.py
"""Tests for PlayerState dataclass."""

import pytest
from src.player.state import PlayerState, _fmt_time


class TestPlayerState:

    def test_initial_state_is_inactive(self):
        state = PlayerState()
        assert state.is_active is False
        assert state.platform is None
        assert state.is_paused is True

    def test_reset_clears_all_fields(self):
        state = PlayerState(
            is_active=True, platform="rutube", title="Test",
            url="https://rutube.ru", position_seconds=300,
            volume=50, is_paused=False,
        )
        state.reset()
        assert state.is_active is False
        assert state.platform is None
        assert state.title is None
        assert state.url is None
        assert state.position_seconds == 0
        assert state.volume == 100
        assert state.is_paused is True
        assert state.search_results == []

    def test_update_from_js(self):
        state = PlayerState()
        state.update_from_js({
            "current_time": 125,
            "duration": 3600,
            "volume": 75,
            "paused": False,
            "muted": True,
        })
        assert state.position_seconds == 125
        assert state.duration_seconds == 3600
        assert state.volume == 75
        assert state.is_paused is False
        assert state.is_muted is True
        assert state.last_command_at is not None

    def test_update_from_js_partial(self):
        """Missing keys should keep existing values."""
        state = PlayerState(volume=80)
        state.update_from_js({"current_time": 10})
        assert state.volume == 80  # unchanged

    def test_format_position_zero(self):
        state = PlayerState()
        assert state.format_position() == "0:00 / 0:00"

    def test_format_position_hours(self):
        state = PlayerState(position_seconds=3723, duration_seconds=9000)
        pos = state.format_position()
        assert "1:02:03" in pos


class TestFmtTime:

    @pytest.mark.parametrize("secs,expected", [
        (0,    "0:00"),
        (59,   "0:59"),
        (60,   "1:00"),
        (90,   "1:30"),
        (3600, "1:00:00"),
        (3723, "1:02:03"),
        (7384, "2:03:04"),
    ])
    def test_format(self, secs, expected):
        assert _fmt_time(secs) == expected
