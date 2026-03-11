# src/utils/system_info.py
"""
System information utilities for /status command.
Этап 6: расширен — показывает версию, платформу, uptime, модель Whisper.
"""

import platform
import sys
from datetime import datetime

from src.config.constants import APP_VERSION, DEFAULT_WHISPER_MODEL

_start_time: datetime = datetime.now()


def get_uptime_str() -> str:
    """Return human-readable uptime since process start."""
    delta = datetime.now() - _start_time
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}ч {minutes}мин"
    elif minutes > 0:
        return f"{minutes}мин {seconds}сек"
    return f"{seconds}сек"


def get_platform_info() -> str:
    """Return OS name and version string."""
    system = platform.system()
    if system == "Darwin":
        return f"macOS {platform.mac_ver()[0]}"
    elif system == "Windows":
        return f"Windows {platform.release()}"
    return f"{system} {platform.release()}"


def get_python_version() -> str:
    """Return Python version string."""
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def format_status_message(
    current_url: str | None = None,
    whisper_model: str | None = None,
    version: str | None = None,
    watchdog_restarts: int | None = None,
    ocr_available: bool | None = None,
) -> str:
    """
    Format /status command response.
    Показывает: версию, платформу, Python, Whisper, uptime, браузер, watchdog, OCR.
    """
    _version = version or APP_VERSION
    _whisper = whisper_model or DEFAULT_WHISPER_MODEL

    lines = [
        "🟢 <b>Бот активен</b>",
        "",
        f"📦 Версия: <code>{_version}</code>",
        f"💻 Платформа: <code>{get_platform_info()}</code>",
        f"🐍 Python: <code>{get_python_version()}</code>",
        f"🎙 Whisper: <code>{_whisper}</code>",
        f"⏱ Uptime: <code>{get_uptime_str()}</code>",
    ]

    if current_url:
        lines.append(f"🌐 URL: <code>{current_url[:80]}</code>")
    else:
        lines.append("🌐 Браузер: <i>не активен</i>")

    if watchdog_restarts is not None:
        wd_icon = "🔄" if watchdog_restarts > 0 else "✅"
        lines.append(f"{wd_icon} Watchdog: <code>{watchdog_restarts}</code> перезапусков")

    if ocr_available is not None:
        ocr_icon = "✅" if ocr_available else "⚠️"
        ocr_label = "активен" if ocr_available else "не установлен (pip install easyocr)"
        lines.append(f"{ocr_icon} OCR: {ocr_label}")

    return "\n".join(lines)
