# src/system/windows_commands.py
"""
Windows system commands: sleep, lock, volume, clipboard, system info.
Тот же публичный интерфейс что и macos_commands.py.
Импортируется автоматически через get_system_commands() на Windows.
"""

import subprocess
from dataclasses import dataclass

from loguru import logger


@dataclass
class SystemInfo:
    """System resource snapshot — identical structure to macOS version."""

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
    """Put Windows PC to sleep."""
    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                   check=True, timeout=10)
    logger.info("System: sleep command sent (Windows)")


async def lock_screen() -> None:
    """Lock Windows screen."""
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"],
                   check=True, timeout=10)
    logger.info("System: screen locked (Windows)")


async def set_system_volume(level: int) -> int:
    """
    Set Windows system volume 0–100 via PowerShell.
    Returns the clamped level actually set.
    """
    clamped = max(0, min(100, level))
    ps_script = (
        f"$obj = New-Object -ComObject WScript.Shell; "
        f"$obj.SendKeys([char]173);" * 50 +  # mute first
        # Use nircmd if available, otherwise PowerShell audio API
        f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)"
    )
    # Более надёжный метод через nircmd (устанавливается в setup_windows.ps1)
    try:
        subprocess.run(
            ["nircmd.exe", "setsysvolume", str(int(clamped * 655.35))],
            check=True, timeout=5,
        )
    except FileNotFoundError:
        logger.warning("nircmd not found; using PowerShell fallback for volume")
        subprocess.run(
            ["powershell", "-Command",
             f"$vol = {clamped / 100.0}; "
             "[audio]::Volume = $vol"],
            timeout=10,
        )
    logger.info(f"System: volume set to {clamped} (Windows)")
    return clamped


async def toggle_system_mute() -> None:
    """Toggle Windows system mute via SendKeys."""
    subprocess.run(
        ["powershell", "-Command",
         "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
        timeout=10,
    )
    logger.info("System: mute toggled (Windows)")


async def copy_to_clipboard(text: str) -> None:
    """Copy text to Windows clipboard via PowerShell."""
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard '{text}'"],
        check=True, timeout=5,
    )
    logger.info(f"System: copied to clipboard ({len(text)} chars) (Windows)")


async def get_system_info() -> SystemInfo:
    """Return current system metrics using psutil."""
    import psutil
    from src.utils.system_info import get_uptime_str

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    return SystemInfo(
        cpu_percent=psutil.cpu_percent(interval=1),
        ram_used_gb=round(mem.used / 1e9, 1),
        ram_total_gb=round(mem.total / 1e9, 1),
        ram_percent=mem.percent,
        disk_free_gb=round(disk.free / 1e9, 1),
        disk_percent=disk.percent,
        uptime_str=get_uptime_str(),
    )
