# src/platform/service_manager.py
"""
Abstract service manager interface + platform detection.
Изолирует платформозависимый код — бизнес-логика не знает об ОС.
Переключение macOS → Windows не требует изменений в остальном коде.
"""

import platform
from abc import ABC, abstractmethod


class ServiceManager(ABC):
    """
    Abstract base for platform-specific service managers.
    Реализации: LaunchdManager (macOS), WindowsServiceManager (Windows, Этап 8).
    """

    @abstractmethod
    def install(self) -> None:
        """Install bot as a system service."""
        ...

    @abstractmethod
    def uninstall(self) -> None:
        """Remove bot from system services."""
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the service."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the service."""
        ...

    @abstractmethod
    def status(self) -> str:
        """Return human-readable service status."""
        ...


def get_service_manager() -> ServiceManager:
    """
    Return platform-appropriate service manager.
    Windows-реализация добавляется в Этапе 8 без изменения этой функции.
    """
    system = platform.system()

    if system == "Darwin":
        from src.platform.launchd import LaunchdManager

        return LaunchdManager()
    elif system == "Windows":
        # Реализуется в Этапе 8
        from src.platform.windows_service import WindowsServiceManager  # type: ignore[import]

        return WindowsServiceManager()
    else:
        raise NotImplementedError(
            f"Platform '{system}' is not supported. "
            f"Supported: macOS (Darwin), Windows."
        )
