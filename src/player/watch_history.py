# src/player/watch_history.py
"""
Watch history with playback position persistence.
Автосохранение позиции каждые 30 сек → «Продолжить с XX:XX» при следующем открытии.
Данные хранятся локально в JSON. Никаких облаков, никаких БД.
"""

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config.constants import DEFAULT_MAX_HISTORY_ITEMS
from src.config.paths import get_watch_history_file


def save_position(
    url: str,
    title: str,
    platform: str,
    position_sec: int,
    duration_sec: int,
) -> None:
    """
    Persist current playback position to local JSON.
    Вызывается каждые POSITION_SAVE_INTERVAL_SEC секунд во время воспроизведения.
    Не бросает исключение — ошибки только логируются.
    """
    try:
        history = _load()
        history[url] = {
            "title":        title,
            "platform":     platform,
            "position_sec": position_sec,
            "duration_sec": duration_sec,
            "last_watched": datetime.now().isoformat(),
        }
        # Оставляем только последние MAX_HISTORY_ITEMS записей
        if len(history) > DEFAULT_MAX_HISTORY_ITEMS:
            oldest_key = min(history, key=lambda k: history[k]["last_watched"])
            del history[oldest_key]
        _save(history)
    except Exception as e:
        logger.error(f"Failed to save watch position for {url}: {e}")


def get_position(url: str) -> dict | None:
    """
    Return saved playback position for URL, or None if not in history.
    Используется при открытии видео — предлагаем «Продолжить с XX:XX».
    """
    try:
        return _load().get(url)
    except Exception as e:
        logger.error(f"Failed to read watch history: {e}")
        return None


def get_recent_history(limit: int = 20) -> list[dict]:
    """Return last N watched items sorted by date descending."""
    try:
        history = _load()
        items = [{"url": k, **v} for k, v in history.items()]
        return sorted(items, key=lambda x: x["last_watched"], reverse=True)[:limit]
    except Exception as e:
        logger.error(f"Failed to read watch history: {e}")
        return []


def clear_history() -> int:
    """Clear entire watch history. Returns number of removed items."""
    try:
        count = len(_load())
        _save({})
        return count
    except Exception as e:
        logger.error(f"Failed to clear watch history: {e}")
        return 0


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

def _load() -> dict:
    path = get_watch_history_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    path = get_watch_history_file()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
