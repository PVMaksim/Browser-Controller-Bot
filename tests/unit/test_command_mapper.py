# tests/unit/test_command_mapper.py
"""
Tests for VoiceCommandMapper: Russian speech → bot command.
"""

import pytest

from src.voice.command_mapper import VoiceCommandMapper
from src.core.command_parser import ParsedCommand


@pytest.fixture
def mapper():
    return VoiceCommandMapper()


class TestNavigationCommands:

    @pytest.mark.parametrize("phrase,expected_cmd,arg_contains", [
        ("открой ютуб",               "open",   "youtube.com"),
        ("Открой YouTube",             "open",   "youtube.com"),
        ("открой https://example.com", "open",   "example.com"),
        ("зайди на вк",                "open",   "vk.com"),
        ("перейди в яндекс",           "open",   "yandex.ru"),
        ("найди рецепт борща",         "search", "рецепт борща"),
        ("поищи котиков",              "search", "котиков"),
        ("ищи python tutorial",        "search", "python"),
        ("сделай скриншот",            "shot",   None),
        ("скриншот",                   "shot",   None),
        ("закрой вкладку",             "close",  None),
        ("закрой браузер",             "close",  None),
        ("какой статус",               "status", None),
        ("статус",                     "status", None),
    ])
    def test_navigation_phrases(self, mapper, phrase, expected_cmd, arg_contains):
        result = mapper.map(phrase)
        assert result is not None, f"No command from: '{phrase}'"
        assert result.command == expected_cmd
        if arg_contains:
            assert arg_contains in (result.argument or ""), \
                f"Expected '{arg_contains}' in '{result.argument}' (from '{phrase}')"


class TestMediaCommands:

    @pytest.mark.parametrize("phrase,expected_cmd", [
        ("поставь на паузу",       "pause"),
        ("пауза",                  "pause"),
        ("продолжи",               "play"),
        ("возобнови",              "play"),
        ("играй",                  "play"),
        ("выключи звук",           "mute"),
        ("тишина",                 "mute"),
        ("статус плеера",          "mediastat"),
        ("что сейчас играет",      "mediastat"),
    ])
    def test_media_commands(self, mapper, phrase, expected_cmd):
        result = mapper.map(phrase)
        assert result is not None, f"No command from: '{phrase}'"
        assert result.command == expected_cmd

    @pytest.mark.parametrize("phrase,expected_arg", [
        ("перемотай назад на 30 секунд",  "30"),
        ("перемотай вперёд на 60 секунд", "60"),
        ("перемотай вперед на 5 минут",   "300"),
        ("перемотай назад на 2 минуты",   "120"),
    ])
    def test_seek_commands_extract_seconds(self, mapper, phrase, expected_arg):
        result = mapper.map(phrase)
        assert result is not None
        assert result.command in ("rewind", "forward")
        assert result.argument == expected_arg

    @pytest.mark.parametrize("phrase,expected_arg", [
        ("сделай погромче",                  "+20"),
        ("увеличь громкость",                "+20"),
        ("потише",                           "-20"),
        ("уменьши громкость",                "-20"),
        ("установи громкость 50",            "50"),
        ("поставь громкость 80",             "80"),
    ])
    def test_volume_commands(self, mapper, phrase, expected_arg):
        result = mapper.map(phrase)
        assert result is not None
        assert result.command == "vol"
        assert result.argument == expected_arg

    @pytest.mark.parametrize("phrase,arg_platform,arg_contains", [
        (
            "найди фильм Интерстеллар на рутубе",
            "rutube",
            "Интерстеллар",
        ),
        (
            "поищи сериал Слово пацана в вк",
            "vk",
            "Слово пацана",
        ),
        (
            "найди видео котики на ютубе",
            "youtube",
            "котики",
        ),
    ])
    def test_find_on_platform(self, mapper, phrase, arg_platform, arg_contains):
        result = mapper.map(phrase)
        assert result is not None
        assert result.command == "find"
        assert arg_platform in (result.argument or "")
        assert arg_contains in (result.argument or "")


class TestSystemCommands:

    @pytest.mark.parametrize("phrase,expected_cmd", [
        ("усыпи мак",             "sleep"),
        ("заблокируй экран",      "lock"),
        ("блокировка",            "lock"),
        ("системная информация",  "sysinfo"),
        ("информация о системе",  "sysinfo"),
    ])
    def test_system_commands(self, mapper, phrase, expected_cmd):
        result = mapper.map(phrase)
        assert result is not None, f"No command from: '{phrase}'"
        assert result.command == expected_cmd


class TestMapperEdgeCases:

    def test_empty_string_returns_none(self, mapper):
        assert mapper.map("") is None

    def test_none_returns_none(self, mapper):
        assert mapper.map(None) is None  # type: ignore[arg-type]

    def test_gibberish_returns_none(self, mapper):
        assert mapper.map("абракадабра непонятное бессмыслица") is None

    def test_returns_parsed_command_type(self, mapper):
        result = mapper.map("статус")
        assert isinstance(result, ParsedCommand)

    def test_case_insensitive(self, mapper):
        r1 = mapper.map("СКРИНШОТ")
        r2 = mapper.map("скриншот")
        assert r1 is not None
        assert r2 is not None
        assert r1.command == r2.command

    def test_fallback_to_text_parser(self, mapper):
        """Фразы без голосового паттерна должны попадать в TextParser."""
        # "screenshot" — нет в _ALL_MAPPINGS, но есть в CommandParser
        result = mapper.map("screenshot")
        assert result is not None
        assert result.command == "shot"
