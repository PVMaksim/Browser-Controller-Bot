# src/config/settings.py
"""
Unified configuration loader and writer.
Читает config.json (distribution) или .env (development).
В Этапе 5 добавлены save() и set() для onboarding-регистрации.
Бизнес-логика не знает, откуда берётся конфиг — только через get()/require().
"""

import json
import os
import stat
from pathlib import Path
from typing import Any

from src.config.paths import get_config_file


class Settings:
    """
    Unified config loader/writer for dev (.env) and distribution (config.json).

    Жизненный цикл в distribution:
    1. Первый запуск → config.json не существует → onboarding mode
    2. /register → set("ALLOWED_USER_ID", ...) → save() → перезапуск
    3. После перезапуска → config.json существует → нормальный режим
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------ #
    # Read                                                                 #
    # ------------------------------------------------------------------ #

    def _load(self) -> dict[str, Any]:
        """
        Load config from config.json if it exists, otherwise fall back to .env.
        config.json используется в distribution-сборке (Этап 5+).
        """
        config_file = get_config_file()
        if config_file.exists():
            try:
                return json.loads(config_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}

        try:
            from dotenv import dotenv_values
            return dict(dotenv_values(".env"))
        except ImportError:
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """Return config value by key, or default if not found."""
        return self._data.get(key, default)

    def require(self, key: str) -> str:
        """
        Return config value, raising ValueError if missing or empty.
        Используется для обязательных параметров при старте бота.
        """
        value = self._data.get(key)
        if not value:
            raise ValueError(
                f"Required config key '{key}' is missing. "
                "Check your .env file or config.json."
            )
        return str(value)

    def is_onboarding_mode(self) -> bool:
        """
        Return True if the bot is in onboarding mode (no owner registered yet).
        В onboarding-режиме бот принимает только команду /register.
        """
        return not bool(self._data.get("ALLOWED_USER_ID"))

    # ------------------------------------------------------------------ #
    # Write (used by onboarding only)                                      #
    # ------------------------------------------------------------------ #

    def set(self, key: str, value: Any) -> None:
        """
        Set config value in memory. Must call save() to persist.
        Изменения в памяти не переживают перезапуск без save().
        """
        self._data[key] = value

    def save(self) -> None:
        """
        Persist current config to config.json with secure permissions (600).
        Создаёт файл и все промежуточные директории.
        Используется только в onboarding — в нормальном режиме конфиг read-only.
        """
        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Пишем атомарно через временный файл — не оставляем частично записанный конфиг
        tmp_file = config_file.with_suffix(".json.tmp")
        try:
            tmp_file.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_file.rename(config_file)
        except OSError:
            tmp_file.unlink(missing_ok=True)
            raise

        # chmod 600 — только владелец может читать/писать
        try:
            config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # На некоторых ФС chmod не поддерживается — некритично

    def reload(self) -> None:
        """
        Reload config from disk into memory.
        Вызывается после save() чтобы применить изменения без перезапуска процесса.
        """
        self._data = self._load()
