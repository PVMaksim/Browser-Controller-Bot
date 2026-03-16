# src/voice/command_mapper.py
"""
Maps transcribed Russian (and English) speech to bot commands.
Работает поверх CommandParser — добавляет специфичные для голоса паттерны:
составные фразы, медиакоманды (Этап 4.5), системные команды (Этап 4.5).

Архитектура: каждый маппер — список (pattern, command, arg_extractor).
Паттерны проверяются сверху вниз, первое совпадение побеждает.
"""

import re
from dataclasses import dataclass
from typing import Callable

from loguru import logger

from src.core.command_parser import CommandParser, ParsedCommand


@dataclass
class VoiceMapping:
    """Single voice phrase → command mapping rule."""

    # Регулярное выражение для сопоставления фразы (re.IGNORECASE всегда)
    pattern: str
    # Целевая команда бота
    command: str
    # Функция извлечения аргумента из match-объекта (None = нет аргумента)
    extract_arg: Callable[[re.Match], str | None] | None = None


# ------------------------------------------------------------------ #
# Mapping rules (order matters — first match wins)                    #
# ------------------------------------------------------------------ #

# Голосовые команды навигации
_NAV_MAPPINGS: list[VoiceMapping] = [
    VoiceMapping(
        pattern=r"открой\s+(.+)",
        command="open",
        extract_arg=lambda m: _resolve_site(m.group(1).strip()),
    ),
    VoiceMapping(
        pattern=r"(?:зайди|перейди)\s+(?:на|в)\s+(.+)",
        command="open",
        extract_arg=lambda m: _resolve_site(m.group(1).strip()),
    ),
    VoiceMapping(
        pattern=r"(?:найди|ищи|поищи|поиск)\s+(.+)",
        command="search",
        extract_arg=lambda m: m.group(1).strip(),
    ),
    VoiceMapping(
        pattern=r"(?:сделай\s+)?скриншот|сними экран",
        command="shot",
    ),
    VoiceMapping(
        pattern=r"закрой\s+(?:вкладку|страницу|браузер)?",
        command="close",
    ),
    VoiceMapping(
        pattern=r"(?:какой\s+)?статус|как\s+дела",
        command="status",
    ),
]

# Голосовые команды медиапульта (Этап 4.5)
_MEDIA_MAPPINGS: list[VoiceMapping] = [
    VoiceMapping(
        pattern=r"(?:найди|поищи)\s+(?:фильм|сериал|видео)?\s*(.+?)\s+(?:на|в)\s+(ютубе?|youtube|рутубе?|rutube|вк|vk|одноклассниках?|ok)",
        command="find",
        extract_arg=lambda m: f"{_normalize_platform(m.group(2))} {m.group(1).strip()}",
    ),
    VoiceMapping(
        pattern=r"поставь\s+(?:на\s+)?паузу|пауза",
        command="pause",
    ),
    VoiceMapping(
        pattern=r"продолжи(?:й)?(?:\s+(?:просмотр|воспроизведение))?|возобнови|играй|играть",
        command="play",
    ),
    VoiceMapping(
        pattern=r"перемотай?\s+(?:назад|обратно)\s+(?:на\s+)?(\d+)\s+(?:секунд|сек|с)",
        command="rewind",
        extract_arg=lambda m: m.group(1),
    ),
    VoiceMapping(
        pattern=r"перемотай?\s+(?:вперёд|вперед)\s+(?:на\s+)?(\d+)\s+(?:секунд|сек|с)",
        command="forward",
        extract_arg=lambda m: m.group(1),
    ),
    VoiceMapping(
        pattern=r"перемотай?\s+(?:назад|обратно)\s+(?:на\s+)?(\d+)\s+минут",
        command="rewind",
        extract_arg=lambda m: str(int(m.group(1)) * 60),
    ),
    VoiceMapping(
        pattern=r"перемотай?\s+(?:вперёд|вперед)\s+(?:на\s+)?(\d+)\s+минут",
        command="forward",
        extract_arg=lambda m: str(int(m.group(1)) * 60),
    ),
    VoiceMapping(
        pattern=r"(?:сделай\s+)?погромче|увеличь\s+громкость",
        command="vol",
        extract_arg=lambda m: "+20",
    ),
    VoiceMapping(
        pattern=r"(?:сделай\s+)?потише|уменьши\s+громкость|убавь",
        command="vol",
        extract_arg=lambda m: "-20",
    ),
    VoiceMapping(
        pattern=r"(?:установи|поставь|сделай)\s+громкость\s+(\d+)",
        command="vol",
        extract_arg=lambda m: m.group(1),
    ),
    VoiceMapping(
        pattern=r"(?:выключи|вырубай?|отключи)\s+звук|тишина|без\s+звука",
        command="mute",
    ),
    VoiceMapping(
        pattern=r"статус\s+плеера?|что\s+(?:сейчас\s+)?играет",
        command="mediastat",
    ),
]

# Системные команды macOS (Этап 4.5)
_SYSTEM_MAPPINGS: list[VoiceMapping] = [
    VoiceMapping(
        pattern=r"(?:усыпи|спать|сон)\s+(?:мак|компьютер|mac)?",
        command="sleep",
    ),
    VoiceMapping(
        pattern=r"заблокируй?\s+(?:экран|мак|компьютер)?|блокировка",
        command="lock",
    ),
    VoiceMapping(
        pattern=r"(?:информация|инфо)\s+(?:о\s+)?(?:системе|компьютере)|системная\s+информация",
        command="sysinfo",
    ),
]

_ALL_MAPPINGS = _MEDIA_MAPPINGS + _NAV_MAPPINGS + _SYSTEM_MAPPINGS

# Словарь нормализации названий платформ
_PLATFORM_ALIASES: dict[str, str] = {
    "ютубе": "youtube",
    "youtube": "youtube",
    "ютуб": "youtube",
    "рутубе": "rutube",
    "rutube": "rutube",
    "рутуб": "rutube",
    "вк": "vk",
    "vk": "vk",
    "одноклассниках": "ok",
    "одноклассники": "ok",
    "ok": "ok",
}



# Псевдонимы сайтов для голосовых команд (аналог CommandParser._SITE_ALIASES)
_SITE_ALIASES: dict[str, str] = {
    "ютуб": "youtube.com",
    "youtube": "youtube.com",
    "yt": "youtube.com",
    "гугл": "google.com",
    "google": "google.com",
    "вк": "vk.com",
    "vk": "vk.com",
    "яндекс": "yandex.ru",
    "yandex": "yandex.ru",
    "рутуб": "rutube.ru",
    "rutube": "rutube.ru",
    "твиттер": "twitter.com",
    "twitter": "twitter.com",
    "одноклассники": "ok.ru",
    "ok": "ok.ru",
}


def _resolve_site(raw: str) -> str:
    """Resolve Russian site alias to domain, or return empty string if unrecognized.

    Возвращает пустую строку если слово не распознано как сайт —
    это предотвращает открытие Chromium на мусорных URL типа 'https://вкладку'.
    """
    import re
    stripped = raw.strip().rstrip(".,!?")  # убираем пунктуацию Whisper в конце
    # Если это уже полный URL — возвращаем как есть
    if stripped.startswith(("http://", "https://")):
        return stripped
    # Проверяем словарь псевдонимов
    lower = stripped.lower()
    if lower in _SITE_ALIASES:
        return _SITE_ALIASES[lower]
    # Если содержит точку — скорее всего уже домен (example.com, sub.domain.ru)
    if "." in stripped:
        return stripped
    # Убираем оставшуюся пунктуацию и ищем снова
    cleaned = re.sub(r"[^\w\s\-]", "", lower).strip()
    if cleaned in _SITE_ALIASES:
        return _SITE_ALIASES[cleaned]
    # Одиночное слово без точки и не в словаре — не является доменом.
    # Возвращаем пустую строку, чтобы validate_url отклонила его
    # и пользователь получил ошибку вместо Chromium на "https://вкладку".
    return ""

def _normalize_platform(raw: str) -> str:
    """Normalize Russian platform name to internal platform key."""
    return _PLATFORM_ALIASES.get(raw.lower().strip(), raw.lower().strip())


class VoiceCommandMapper:
    """
    Maps transcribed voice text to structured bot commands.
    Сначала применяет специализированные голосовые паттерны,
    затем fallback на CommandParser (общий парсер текстовых команд).
    """

    def __init__(self) -> None:
        self._text_parser = CommandParser()

    def map(self, text: str) -> ParsedCommand | None:
        """
        Map transcribed text to a bot command.
        Returns ParsedCommand or None if nothing matched.
        """
        if not text or not text.strip():
            return None

        # Нормализуем Unicode — Whisper иногда возвращает омографы или невидимые символы
        import unicodedata
        text_clean = unicodedata.normalize("NFC", text.strip())

        # Шаг 1: голосовые паттерны (более специфичные)
        for mapping in _ALL_MAPPINGS:
            match = re.search(mapping.pattern, text_clean, re.IGNORECASE)
            if match:
                arg = mapping.extract_arg(match) if mapping.extract_arg else None
                logger.debug(f"Voice mapped: '{text_clean}' → {mapping.command}({arg!r})")
                return ParsedCommand(command=mapping.command, argument=arg)

        # Шаг 2: fallback на текстовый парсер
        result = self._text_parser.parse(text_clean)
        if result:
            logger.debug(f"Voice fallback to TextParser: '{text_clean}' → {result.command}")
        else:
            logger.debug(f"Voice: no match for '{text_clean}'")

        return result
