# src/config/paths.py
"""
Cross-platform path resolution using platformdirs.
Никогда не хардкодить пути — всегда через эти функции.

macOS paths:
  data:    ~/Library/Application Support/SecureBrowserBot
  logs:    ~/Library/Logs/SecureBrowserBot
  cache:   ~/Library/Caches/SecureBrowserBot

Windows paths:
  data:    C:\\Users\\user\\AppData\\Roaming\\SecureBrowserBot
  logs:    C:\\Users\\user\\AppData\\Local\\SecureBrowserBot\\Logs
  cache:   C:\\Users\\user\\AppData\\Local\\SecureBrowserBot\\Cache
"""

from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir, user_log_dir

from src.config.constants import APP_NAME


def get_data_dir() -> Path:
    """
    Return platform-appropriate user data directory.
    Создаёт папку при первом обращении.
    """
    path = Path(user_data_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    """
    Return platform-appropriate log directory.
    Создаёт папку при первом обращении.
    """
    path = Path(user_log_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    """Return platform-appropriate cache directory."""
    path = Path(user_cache_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_file() -> Path:
    """
    Return path to config.json.
    Используется в distribution-сборке вместо .env.
    """
    return get_data_dir() / "config.json"


def get_browser_profile_dir() -> Path:
    """
    Return isolated browser profile directory.
    Изолированный профиль — обязательное требование безопасности.
    """
    return get_cache_dir() / "browser_profile"


def get_voice_tmp_dir() -> Path:
    """
    Return temp directory for voice file processing.
    Файлы создаются здесь и гарантированно удаляются через finally.
    """
    path = Path("tmp")
    path.mkdir(exist_ok=True)
    return path


def get_watch_history_file() -> Path:
    """Return path to watch history JSON file (Stage 4.5)."""
    return get_data_dir() / "watch_history.json"


def get_watchlist_file() -> Path:
    """Return path to watchlist JSON file (Stage 4.5)."""
    return get_data_dir() / "watchlist.json"
