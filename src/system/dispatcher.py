# src/system/dispatcher.py
"""
Platform-aware system commands dispatcher.
Возвращает правильный модуль в зависимости от ОС.
Хендлер (system_commands.py) импортирует отсюда — не знает о конкретной платформе.
"""

import platform
from types import ModuleType


def get_system_commands() -> ModuleType:
    """
    Return platform-appropriate system commands module.
    macOS → macos_commands, Windows → windows_commands.
    Raises NotImplementedError on unsupported platforms.
    """
    system = platform.system()
    if system == "Darwin":
        from src.system import macos_commands
        return macos_commands
    elif system == "Windows":
        from src.system import windows_commands
        return windows_commands
    else:
        raise NotImplementedError(
            f"System commands not supported on {system}. "
            "Supported: macOS (Darwin), Windows."
        )
