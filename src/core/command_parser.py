# src/core/command_parser.py
"""
Command parser: converts text or transcribed voice input to structured commands.
Обрабатывает как явные команды (/open, /search), так и свободный текст на русском.
"""

from dataclasses import dataclass

from src.utils.validators import normalize_url, sanitize_search_query

# Словари для маппинга русских фраз на команды
# Будут расширены в src/voice/command_mapper.py для голосовых команд (Этап 3)
_OPEN_KEYWORDS = ("открой", "открыть", "зайди", "перейди на", "go to", "open")
_SEARCH_KEYWORDS = ("найди", "ищи", "поищи", "search", "поиск")
_SHOT_KEYWORDS = ("скриншот", "снимок", "screenshot", "сделай скриншот", "shot")
_CLOSE_KEYWORDS = ("закрой", "закрыть", "закрой вкладку", "close")
_STATUS_KEYWORDS = ("статус", "status", "какой статус", "как дела")
_STOP_KEYWORDS = ("стоп", "stop", "остановись", "выключись")

# Словарь популярных сайтов для удобного ввода
_SITE_ALIASES: dict[str, str] = {
    "ютуб": "youtube.com",
    "youtube": "youtube.com",
    "yt": "youtube.com",
    "гугл": "google.com",
    "google": "google.com",
    "вк": "vk.com",
    "vk": "vk.com",
    "рутуб": "rutube.ru",
    "rutube": "rutube.ru",
    "яндекс": "yandex.ru",
    "yandex": "yandex.ru",
    "твич": "twitch.tv",
    "twitch": "twitch.tv",
}


@dataclass
class ParsedCommand:
    """Structured result of command parsing."""

    command: str  # "open" | "search" | "shot" | "close" | "status" | "stop"
    argument: str | None = None  # URL for "open", query for "search"


class CommandParser:
    """
    Parses free-form text (from text or voice) into structured bot commands.
    Поддерживает русские фразы, псевдонимы сайтов и прямые команды бота.
    """

    def parse(self, text: str) -> ParsedCommand | None:
        """
        Parse text into a structured command.
        Возвращает None если команда не распознана.
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # Проверяем каждый тип команды по ключевым словам
        for keyword in _SHOT_KEYWORDS:
            if keyword in text_lower:
                return ParsedCommand(command="shot")

        for keyword in _CLOSE_KEYWORDS:
            if keyword in text_lower:
                return ParsedCommand(command="close")

        for keyword in _STATUS_KEYWORDS:
            if keyword in text_lower:
                return ParsedCommand(command="status")

        for keyword in _STOP_KEYWORDS:
            if keyword in text_lower:
                return ParsedCommand(command="stop")

        for keyword in _OPEN_KEYWORDS:
            if text_lower.startswith(keyword):
                argument = text[len(keyword):].strip()
                url = self._resolve_url(argument)
                return ParsedCommand(command="open", argument=url)

        for keyword in _SEARCH_KEYWORDS:
            if text_lower.startswith(keyword):
                query = text[len(keyword):].strip()
                return ParsedCommand(
                    command="search",
                    argument=sanitize_search_query(query),
                )

        return None

    def _resolve_url(self, raw: str) -> str:
        """
        Resolve site alias or normalize raw URL.
        'ютуб' → 'youtube.com', 'example.com' → 'https://example.com'
        """
        raw_lower = raw.lower().strip()
        if raw_lower in _SITE_ALIASES:
            return normalize_url(_SITE_ALIASES[raw_lower])
        return normalize_url(raw)
