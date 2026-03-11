# tests/unit/test_platform_dispatcher.py
"""Tests for cross-platform system commands dispatcher."""

import pytest
from unittest.mock import patch, MagicMock


class TestSystemDispatcher:

    def test_returns_macos_module_on_darwin(self):
        with patch("platform.system", return_value="Darwin"):
            from src.system.dispatcher import get_system_commands
            mod = get_system_commands()
            assert mod.__name__ == "src.system.macos_commands"

    def test_returns_windows_module_on_windows(self):
        with patch("platform.system", return_value="Windows"):
            from src.system.dispatcher import get_system_commands
            mod = get_system_commands()
            assert mod.__name__ == "src.system.windows_commands"

    def test_raises_on_unsupported_platform(self):
        with patch("platform.system", return_value="Linux"):
            from src.system.dispatcher import get_system_commands
            with pytest.raises(NotImplementedError, match="Linux"):
                get_system_commands()

    def test_macos_module_has_required_functions(self):
        """Обе платформы должны иметь одинаковый публичный интерфейс."""
        from src.system import macos_commands
        required = ["sleep_mac", "lock_screen", "set_system_volume",
                    "toggle_system_mute", "copy_to_clipboard", "get_system_info"]
        for fn in required:
            assert hasattr(macos_commands, fn), f"macos_commands missing: {fn}"

    def test_windows_module_has_required_functions(self):
        """Windows-модуль должен иметь те же функции что и macOS-модуль."""
        from src.system import windows_commands
        required = ["sleep_mac", "lock_screen", "set_system_volume",
                    "toggle_system_mute", "copy_to_clipboard", "get_system_info"]
        for fn in required:
            assert hasattr(windows_commands, fn), f"windows_commands missing: {fn}"
