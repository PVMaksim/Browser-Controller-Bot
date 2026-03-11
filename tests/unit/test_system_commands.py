# tests/unit/test_system_commands.py
"""Tests for macOS system commands (mocked subprocess)."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestSetSystemVolume:

    @pytest.mark.asyncio
    async def test_clamps_above_100(self):
        from src.system.macos_commands import set_system_volume
        with patch("src.system.macos_commands._run_osascript") as mock_run:
            result = await set_system_volume(150)
            assert result == 100
            called_script = mock_run.call_args[0][0]
            assert "100" in called_script

    @pytest.mark.asyncio
    async def test_clamps_below_0(self):
        from src.system.macos_commands import set_system_volume
        with patch("src.system.macos_commands._run_osascript") as mock_run:
            result = await set_system_volume(-10)
            assert result == 0

    @pytest.mark.asyncio
    async def test_valid_value_passes_through(self):
        from src.system.macos_commands import set_system_volume
        with patch("src.system.macos_commands._run_osascript"):
            result = await set_system_volume(75)
            assert result == 75


class TestCopyToClipboard:

    @pytest.mark.asyncio
    async def test_calls_pbcopy(self):
        from src.system.macos_commands import copy_to_clipboard
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            await copy_to_clipboard("Hello World")
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["pbcopy"]

    @pytest.mark.asyncio
    async def test_pbcopy_failure_raises(self):
        from src.system.macos_commands import copy_to_clipboard
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(RuntimeError, match="pbcopy failed"):
                await copy_to_clipboard("text")


class TestRunOsascript:

    def test_successful_call(self):
        from src.system.macos_commands import _run_osascript
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _run_osascript("set volume output volume 50")
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "osascript" in args

    def test_nonzero_exit_raises(self):
        from src.system.macos_commands import _run_osascript
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error message")
            with pytest.raises(RuntimeError, match="osascript error"):
                _run_osascript("bad script")


class TestSystemInfo:

    @pytest.mark.asyncio
    async def test_returns_system_info_object(self):
        from src.system.macos_commands import get_system_info, SystemInfo
        mock_mem = MagicMock(used=4e9, total=16e9, percent=25.0)
        mock_disk = MagicMock(free=200e9, percent=40.0)
        with patch("psutil.cpu_percent", return_value=30.0), \
             patch("psutil.virtual_memory", return_value=mock_mem), \
             patch("psutil.disk_usage", return_value=mock_disk):
            info = await get_system_info()
            assert isinstance(info, SystemInfo)
            assert info.cpu_percent == 30.0
            assert info.ram_percent == 25.0

    def test_format_telegram(self):
        from src.system.macos_commands import SystemInfo
        info = SystemInfo(
            cpu_percent=45.0,
            ram_used_gb=8.0,
            ram_total_gb=16.0,
            ram_percent=50.0,
            disk_free_gb=100.0,
            disk_percent=60.0,
            uptime_str="2ч 30мин",
        )
        text = info.format_telegram()
        assert "CPU" in text
        assert "45%" in text
        assert "RAM" in text
        assert "2ч 30мин" in text
