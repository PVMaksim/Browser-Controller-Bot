# src/system/macos_commands.py
"""
macOS system commands: sleep, lock, volume, clipboard, system info.
Все функции изолированы в этом файле.
В Этапе 8 создаётся windows_commands.py с тем же публичным интерфейсом.
"""

import subprocess
from dataclasses import dataclass

from loguru import logger


@dataclass
class SystemInfo:
    """System resource snapshot for /sysinfo command."""

    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_free_gb: float
    disk_percent: float
    uptime_str: str

    def format_telegram(self) -> str:
        """Format as Telegram HTML message."""
        return (
            "💻 <b>Состояние системы</b>\n\n"
            f"🔲 CPU:    {self.cpu_percent:.0f}%\n"
            f"🧠 RAM:    {self.ram_used_gb:.1f} ГБ / {self.ram_total_gb:.1f} ГБ"
            f"  ({self.ram_percent:.0f}%)\n"
            f"💾 Диск:   {self.disk_free_gb:.0f} ГБ свободно"
            f"  ({100 - self.disk_percent:.0f}% своб.)\n"
            f"⏱ Uptime: {self.uptime_str}"
        )


async def sleep_mac() -> None:
    """Put Mac to sleep via osascript."""
    _run_osascript('tell application "System Events" to sleep')
    logger.info("System: sleep command sent")


async def lock_screen() -> None:
    """Lock Mac screen via keyboard shortcut (Ctrl+Cmd+Q)."""
    _run_osascript(
        'tell application "System Events" to '
        'keystroke "q" using {control down, command down}'
    )
    logger.info("System: screen lock command sent")


async def set_system_volume(level: int) -> int:
    """
    Set macOS system output volume 0–100.
    Returns the clamped level that was actually set.
    """
    clamped = max(0, min(100, level))
    _run_osascript(f"set volume output volume {clamped}")
    logger.info(f"System: volume set to {clamped}")
    return clamped


async def toggle_system_mute() -> None:
    """Toggle system audio mute via osascript."""
    _run_osascript("set volume output muted not (output muted of (get volume settings))")
    logger.info("System: mute toggled")


async def copy_to_clipboard(text: str) -> None:
    """Copy text to macOS clipboard via pbcopy."""
    result = subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("pbcopy failed")
    logger.info(f"System: copied to clipboard ({len(text)} chars)")


async def get_system_info() -> SystemInfo:
    """
    Return current system metrics using psutil.
    Требует psutil в requirements.txt — уже добавлен.
    """
    import psutil
    from src.utils.system_info import get_uptime_str

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return SystemInfo(
        cpu_percent=psutil.cpu_percent(interval=1),
        ram_used_gb=round(mem.used / 1e9, 1),
        ram_total_gb=round(mem.total / 1e9, 1),
        ram_percent=mem.percent,
        disk_free_gb=round(disk.free / 1e9, 1),
        disk_percent=disk.percent,
        uptime_str=get_uptime_str(),
    )


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

def _run_osascript(script: str) -> None:
    """Execute AppleScript via osascript. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"osascript error (code {result.returncode}): {result.stderr.strip()}"
        )
