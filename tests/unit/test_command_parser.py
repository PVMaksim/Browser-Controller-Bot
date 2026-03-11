# tests/unit/test_command_parser.py
"""
Tests for text/voice → structured command conversion.
"""

import pytest

from src.core.command_parser import CommandParser, ParsedCommand


class TestCommandParser:
    """Tests for free-form text to structured command parsing."""

    def setup_method(self):
        self.parser = CommandParser()

    @pytest.mark.parametrize("text,expected_cmd,expected_arg_contains", [
        ("открой ютуб",         "open",   "youtube.com"),
        ("Открой YouTube",      "open",   "youtube.com"),
        ("открой гугл",         "open",   "google.com"),
        ("найди рецепт борща",  "search", "рецепт борща"),
        ("ищи котиков",         "search", "котиков"),
        ("сделай скриншот",     "shot",   None),
        ("скриншот",            "shot",   None),
        ("закрой вкладку",      "close",  None),
        ("закрой",              "close",  None),
        ("какой статус",        "status", None),
        ("статус",              "status", None),
    ])
    def test_russian_phrases(
        self, text: str, expected_cmd: str, expected_arg_contains: str | None
    ):
        result = self.parser.parse(text)
        assert result is not None, f"Expected command from '{text}', got None"
        assert result.command == expected_cmd
        if expected_arg_contains:
            assert expected_arg_contains in (result.argument or "")

    def test_unrecognized_text_returns_none(self):
        result = self.parser.parse("абракадабра непонятное")
        assert result is None

    def test_empty_string_returns_none(self):
        result = self.parser.parse("")
        assert result is None

    def test_none_returns_none(self):
        result = self.parser.parse(None)  # type: ignore[arg-type]
        assert result is None

    def test_open_with_explicit_url(self):
        result = self.parser.parse("открой https://example.com")
        assert result is not None
        assert result.command == "open"
        assert result.argument == "https://example.com"

    def test_open_without_scheme_adds_https(self):
        result = self.parser.parse("открой example.com")
        assert result is not None
        assert result.argument == "https://example.com"

    def test_site_aliases_resolve_correctly(self):
        cases = [
            ("открой вк", "vk.com"),
            ("открой рутуб", "rutube.ru"),
            ("открой яндекс", "yandex.ru"),
        ]
        for text, expected_domain in cases:
            result = self.parser.parse(text)
            assert result is not None
            assert expected_domain in (result.argument or "")

    def test_parsed_command_is_dataclass(self):
        result = self.parser.parse("статус")
        assert isinstance(result, ParsedCommand)
