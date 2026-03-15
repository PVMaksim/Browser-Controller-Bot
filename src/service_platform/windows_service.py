# src/platform/windows_service.py
"""
Windows service manager via NSSM (Non-Sucking Service Manager).
Реализует тот же интерфейс ServiceManager что и LaunchdManager на macOS.
Бизнес-логика не знает, на какой платформе работает — она вызывает
get_service_manager() и получает нужную реализацию.

Требования:
  - NSSM установлен и доступен в PATH (setup_windows.ps1 устанавливает через winget)
  - Скрипт запускается с правами администратора (UAC) при install/uninstall

Использование:
  python -m src.service_platform.cli install   # установить как Windows-сервис
  python -m src.service_platform.cli start
  python -m src.service_platform.cli stop
  python -m src.service_platform.cli status
"""

import subprocess
import sys
from pathlib import Path

from loguru import logger

from src.service_platform.service_manager import ServiceManager

_SERVICE_NAME = "SecureBrowserBot"


class WindowsServiceManager(ServiceManager):
    """
    Manage the bot as a Windows service via NSSM.
    Каждый метод выполняет NSSM-команду и логирует результат.
    """

    def install(self) -> None:
        """
        Install bot as a Windows service via NSSM.
        Требует права администратора.
        """
        exe_path = _get_executable_path()
        _nssm("install", _SERVICE_NAME, str(exe_path))
        # Настраиваем автозапуск и перезапуск при сбое
        _nssm("set", _SERVICE_NAME, "Start", "SERVICE_AUTO_START")
        _nssm("set", _SERVICE_NAME, "AppRestartDelay", "3000")
        logger.info(f"Service '{_SERVICE_NAME}' installed via NSSM")

    def uninstall(self) -> None:
        """Remove Windows service. Требует права администратора."""
        self.stop()
        _nssm("remove", _SERVICE_NAME, "confirm")
        logger.info(f"Service '{_SERVICE_NAME}' removed")

    def start(self) -> None:
        """Start the Windows service."""
        _nssm("start", _SERVICE_NAME)
        logger.info(f"Service '{_SERVICE_NAME}' started")

    def stop(self) -> None:
        """Stop the Windows service (graceful)."""
        _nssm("stop", _SERVICE_NAME)
        logger.info(f"Service '{_SERVICE_NAME}' stopped")

    def status(self) -> str:
        """Return human-readable service status string."""
        try:
            result = subprocess.run(
                ["nssm", "status", _SERVICE_NAME],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip() or result.stderr.strip() or "unknown"
        except FileNotFoundError:
            return "NSSM not found — install it via setup_windows.ps1"
        except Exception as e:
            return f"Error: {e}"


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #

def _nssm(*args: str) -> None:
    """Run an NSSM command, raising RuntimeError on failure."""
    cmd = ["nssm", *args]
    logger.debug(f"NSSM: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode not in (0, 1):  # NSSM returns 1 for some OK states
        raise RuntimeError(
            f"NSSM command failed: {' '.join(args)}\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )


def _get_executable_path() -> Path:
    """
    Return path to the bot executable.
    В distribution-сборке — путь к .exe от PyInstaller.
    В dev-режиме — путь к main.py с текущим интерпретатором Python.
    """
    # PyInstaller упаковывает приложение — sys.frozen=True
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    # Development mode — запускаем через python main.py
    main_py = Path(__file__).parent.parent / "main.py"
    return Path(sys.executable).parent / "python.exe"
