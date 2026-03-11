# tests/unit/test_config_paths.py
"""
Tests for cross-platform path resolution via platformdirs.
Проверяем что пути создаются на любой платформе.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.config.paths import (
    get_browser_profile_dir,
    get_config_file,
    get_data_dir,
    get_log_dir,
    get_voice_tmp_dir,
    get_watch_history_file,
    get_watchlist_file,
)


class TestConfigPaths:
    """Ensure paths resolve correctly and directories are created."""

    def test_data_dir_is_created_if_missing(self, tmp_path):
        with patch("src.config.paths.user_data_dir", return_value=str(tmp_path / "data")):
            result = get_data_dir()
            assert result.exists()
            assert result.is_dir()

    def test_log_dir_is_created_if_missing(self, tmp_path):
        with patch("src.config.paths.user_log_dir", return_value=str(tmp_path / "logs")):
            result = get_log_dir()
            assert result.exists()
            assert result.is_dir()

    def test_browser_profile_dir_contains_expected_name(self, tmp_path):
        with patch("src.config.paths.user_cache_dir", return_value=str(tmp_path)):
            result = get_browser_profile_dir()
            assert isinstance(result, Path)
            assert "browser_profile" in str(result)

    def test_config_file_path_ends_with_json(self, tmp_path):
        with patch("src.config.paths.user_data_dir", return_value=str(tmp_path)):
            result = get_config_file()
            assert result.suffix == ".json"
            assert result.name == "config.json"

    def test_watch_history_file_is_json(self, tmp_path):
        with patch("src.config.paths.user_data_dir", return_value=str(tmp_path)):
            result = get_watch_history_file()
            assert result.suffix == ".json"

    def test_watchlist_file_is_json(self, tmp_path):
        with patch("src.config.paths.user_data_dir", return_value=str(tmp_path)):
            result = get_watchlist_file()
            assert result.suffix == ".json"

    def test_voice_tmp_dir_is_created(self, tmp_path, monkeypatch):
        # Меняем рабочую папку чтобы tmp/ создавался в tmp_path
        monkeypatch.chdir(tmp_path)
        result = get_voice_tmp_dir()
        assert result.exists()
        assert result.is_dir()
