# tests/unit/test_sanitize.py
"""Tests for Telegram text sanitization helpers."""

from src.utils.sanitize import sanitize_caption
from src.config.constants import TELEGRAM_MAX_CAPTION_LENGTH


class TestSanitizeCaption:

    def test_short_text_unchanged(self):
        text = "https://example.com"
        assert sanitize_caption(text) == text

    def test_long_text_truncated(self):
        long_text = "a" * (TELEGRAM_MAX_CAPTION_LENGTH + 100)
        result = sanitize_caption(long_text)
        assert len(result) <= TELEGRAM_MAX_CAPTION_LENGTH

    def test_truncated_text_ends_with_ellipsis(self):
        long_text = "a" * (TELEGRAM_MAX_CAPTION_LENGTH + 100)
        result = sanitize_caption(long_text)
        assert result.endswith("...")

    def test_exact_limit_not_truncated(self):
        text = "x" * TELEGRAM_MAX_CAPTION_LENGTH
        result = sanitize_caption(text)
        assert result == text
        assert not result.endswith("...")
