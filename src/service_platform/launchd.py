# src/platform/launchd.py
"""
macOS launchd service manager implementation.
Управляет автозапуском бота через launchd (LaunchAgent).
"""

import subprocess
from pathlib import Path

from loguru import logger

from src.service_platform.service_manager import ServiceManager

PLIST_LABEL = "com.user.secure-browser-bot"
PLIST_FILENAME = f"{PLIST_LABEL}.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


class LaunchdManager(ServiceManager):
    """macOS launchd service manager using LaunchAgents."""

    def _plist_path(self) -> Path:
        """Return full path to plist file in LaunchAgents."""
        return LAUNCH_AGENTS_DIR / PLIST_FILENAME

    def install(self) -> None:
        """
        Copy plist to ~/Library/LaunchAgents and load it.
        Plist должен находиться в корне проекта.
        """
        source = Path(PLIST_FILENAME)
        if not source.exists():
            raise FileNotFoundError(
                f"Plist file not found: {source}. "
                f"Run scripts/setup_macos.sh first."
            )

        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        dest = self._plist_path()
        dest.write_text(source.read_text())
        logger.info(f"Plist copied to {dest}")

        self.start()

    def uninstall(self) -> None:
        """Unload and remove plist from LaunchAgents."""
        self.stop()
        plist = self._plist_path()
        if plist.exists():
            plist.unlink()
            logger.info(f"Plist removed: {plist}")

    def start(self) -> None:
        """Load and start the launchd service."""
        plist = self._plist_path()
        result = subprocess.run(
            ["launchctl", "load", str(plist)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"launchctl load failed: {result.stderr}")
        else:
            logger.info(f"Service started: {PLIST_LABEL}")

    def stop(self) -> None:
        """Unload the launchd service."""
        plist = self._plist_path()
        if not plist.exists():
            logger.warning(f"Plist not found, cannot stop: {plist}")
            return

        result = subprocess.run(
            ["launchctl", "unload", str(plist)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"launchctl unload failed: {result.stderr}")
        else:
            logger.info(f"Service stopped: {PLIST_LABEL}")

    def status(self) -> str:
        """Return human-readable service status from launchctl."""
        result = subprocess.run(
            ["launchctl", "list", PLIST_LABEL],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return f"✅ Сервис активен ({PLIST_LABEL})"
        return f"❌ Сервис не найден ({PLIST_LABEL})"
