# src/player/watchlist.py
"""
Watch-later list ('Посмотреть позже').
Сохранить видео одной командой, вернуться в любой момент.
Данные хранятся локально в JSON — никаких облаков.
"""

import json
from datetime import datetime

from loguru import logger

from src.config.constants import MAX_WATCHLIST_ITEMS
from src.config.paths import get_watchlist_file


def add_to_watchlist(
    url: str,
    title: str,
    platform: str,
    duration: str | None = None,
) -> bool:
    """
    Add video to watch-later list.
    Не добавляет дубликаты — проверяет по URL.
    Returns True if added, False if already in list or list is full.
    """
    try:
        watchlist = _load()
        if url in watchlist:
            logger.debug(f"Watchlist: URL already present: {url}")
            return False
        if len(watchlist) >= MAX_WATCHLIST_ITEMS:
            logger.warning("Watchlist is full (MAX_WATCHLIST_ITEMS reached)")
            return False
        watchlist[url] = {
            "title":    title,
            "platform": platform,
            "duration": duration,
            "added_at": datetime.now().isoformat(),
        }
        _save(watchlist)
        return True
    except Exception as e:
        logger.error(f"Failed to add to watchlist: {e}")
        return False


def remove_from_watchlist(url: str) -> bool:
    """Remove video from watchlist by URL. Returns True if it was present."""
    try:
        watchlist = _load()
        if url not in watchlist:
            return False
        del watchlist[url]
        _save(watchlist)
        return True
    except Exception as e:
        logger.error(f"Failed to remove from watchlist: {e}")
        return False


def get_watchlist() -> list[dict]:
    """Return all watchlist items sorted by date added (newest first)."""
    try:
        items = [{"url": k, **v} for k, v in _load().items()]
        return sorted(items, key=lambda x: x["added_at"], reverse=True)
    except Exception as e:
        logger.error(f"Failed to read watchlist: {e}")
        return []


def is_in_watchlist(url: str) -> bool:
    """Check if URL is already in watchlist."""
    try:
        return url in _load()
    except Exception:
        return False


def clear_watchlist() -> int:
    """Clear entire watchlist. Returns number of removed items."""
    try:
        count = len(_load())
        _save({})
        return count
    except Exception as e:
        logger.error(f"Failed to clear watchlist: {e}")
        return 0


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

def _load() -> dict:
    path = get_watchlist_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    path = get_watchlist_file()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
