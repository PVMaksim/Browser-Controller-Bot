# tests/unit/test_system_info.py
"""Unit tests for src/utils/system_info.py"""

import sys
from datetime import datetime
from unittest.mock import patch

from src.utils.system_info import (
    format_status_message,
    get_platform_info,
    get_python_version,
    get_uptime_str,
)


class TestGetUptimeStr:
    def test_returns_seconds_for_short_uptime(self):
        fixed = datetime(2024, 1, 1, 12, 0, 0)
        now   = datetime(2024, 1, 1, 12, 0, 45)
        with patch("src.utils.system_info._start_time", fixed), \
             patch("src.utils.system_info.datetime") as mock_dt:
            mock_dt.now.return_value = now
            result = get_uptime_str()
        assert "45сек" in result

    def test_returns_minutes_for_medium_uptime(self):
        fixed = datetime(2024, 1, 1, 12, 0, 0)
        now   = datetime(2024, 1, 1, 12, 5, 20)
        with patch("src.utils.system_info._start_time", fixed), \
             patch("src.utils.system_info.datetime") as mock_dt:
            mock_dt.now.return_value = now
            result = get_uptime_str()
        assert "мин" in result
        assert "ч" not in result

    def test_returns_hours_for_long_uptime(self):
        fixed = datetime(2024, 1, 1, 10, 0, 0)
        now   = datetime(2024, 1, 1, 13, 30, 0)
        with patch("src.utils.system_info._start_time", fixed), \
             patch("src.utils.system_info.datetime") as mock_dt:
            mock_dt.now.return_value = now
            result = get_uptime_str()
        assert "ч" in result

    def test_returns_string(self):
        assert isinstance(get_uptime_str(), str)


class TestGetPlatformInfo:
    def test_returns_string(self):
        assert isinstance(get_platform_info(), str)

    def test_detects_darwin(self):
        with patch("src.utils.system_info.platform.system", return_value="Darwin"), \
             patch("src.utils.system_info.platform.mac_ver", return_value=("14.2", (), "")):
            assert "macOS" in get_platform_info()

    def test_detects_windows(self):
        with patch("src.utils.system_info.platform.system", return_value="Windows"), \
             patch("src.utils.system_info.platform.release", return_value="10"):
            assert "Windows" in get_platform_info()

    def test_fallback_for_linux(self):
        with patch("src.utils.system_info.platform.system", return_value="Linux"), \
             patch("src.utils.system_info.platform.release", return_value="6.5.0"):
            result = get_platform_info()
            assert "Linux" in result


class TestGetPythonVersion:
    def test_returns_string(self):
        assert isinstance(get_python_version(), str)

    def test_contains_major_minor(self):
        v = get_python_version()
        parts = v.split(".")
        assert len(parts) == 3
        assert parts[0] == str(sys.version_info.major)


class TestFormatStatusMessage:
    def test_contains_active_marker(self):
        result = format_status_message()
        assert "Бот активен" in result

    def test_shows_version(self):
        result = format_status_message(version="9.9.9")
        assert "9.9.9" in result

    def test_shows_whisper_model(self):
        result = format_status_message(whisper_model="large")
        assert "large" in result

    def test_shows_url_when_provided(self):
        result = format_status_message(current_url="https://rutube.ru/video/abc")
        assert "rutube.ru" in result

    def test_shows_browser_inactive_when_no_url(self):
        result = format_status_message(current_url=None)
        assert "не активен" in result

    def test_shows_watchdog_restarts_zero(self):
        result = format_status_message(watchdog_restarts=0)
        assert "Watchdog" in result
        assert "✅" in result

    def test_shows_watchdog_restarts_nonzero(self):
        result = format_status_message(watchdog_restarts=3)
        assert "3" in result
        assert "🔄" in result

    def test_omits_watchdog_when_none(self):
        result = format_status_message(watchdog_restarts=None)
        assert "Watchdog" not in result

    def test_shows_ocr_available(self):
        result = format_status_message(ocr_available=True)
        assert "OCR" in result
        assert "✅" in result

    def test_shows_ocr_unavailable(self):
        result = format_status_message(ocr_available=False)
        assert "OCR" in result
        assert "⚠️" in result

    def test_omits_ocr_when_none(self):
        result = format_status_message(ocr_available=None)
        assert "OCR" not in result

    def test_url_truncated_to_80_chars(self):
        long_url = "https://example.com/" + "x" * 100
        result = format_status_message(current_url=long_url)
        # The URL shown should be at most 80 chars
        import re
        match = re.search(r"URL: <code>(.+?)</code>", result)
        assert match and len(match.group(1)) <= 80

    def test_returns_string(self):
        assert isinstance(format_status_message(), str)
