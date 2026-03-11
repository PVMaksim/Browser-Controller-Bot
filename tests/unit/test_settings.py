# tests/unit/test_settings.py
"""Tests for unified config loader/writer (Stage 5: save, set, reload, onboarding_mode)."""

import json
import pytest
from src.config.settings import Settings


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Route Settings file ops to tmp_path."""
    cf = tmp_path / "config.json"
    monkeypatch.setattr("src.config.settings.get_config_file", lambda: cf)
    return cf


class TestSettingsRead:

    def test_reads_from_config_json(self, config_file):
        config_file.write_text(
            json.dumps({"BOT_TOKEN": "tok", "ALLOWED_USER_ID": "123"}), encoding="utf-8"
        )
        s = Settings()
        assert s.get("BOT_TOKEN") == "tok"
        assert s.get("ALLOWED_USER_ID") == "123"

    def test_returns_default_for_missing_key(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        assert s.get("MISSING", "fallback") == "fallback"

    def test_returns_none_when_no_default(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        assert s.get("MISSING") is None

    def test_require_raises_when_missing(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        with pytest.raises(ValueError, match="MISSING"):
            s.require("MISSING")

    def test_require_returns_value(self, config_file):
        config_file.write_text(json.dumps({"BOT_TOKEN": "abc123"}), encoding="utf-8")
        s = Settings()
        assert s.require("BOT_TOKEN") == "abc123"


class TestOnboardingMode:

    def test_onboarding_when_no_user_id(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        assert Settings().is_onboarding_mode() is True

    def test_not_onboarding_when_user_id_set(self, config_file):
        config_file.write_text(
            json.dumps({"ALLOWED_USER_ID": "123456789"}), encoding="utf-8"
        )
        assert Settings().is_onboarding_mode() is False

    def test_onboarding_mode_returns_true_for_empty_data(self, monkeypatch):
        monkeypatch.setattr("src.config.settings.Settings._load", lambda self: {})
        s = Settings()
        assert s.is_onboarding_mode() is True


class TestSettingsWrite:

    def test_set_updates_memory(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        s.set("ALLOWED_USER_ID", "999")
        assert s.get("ALLOWED_USER_ID") == "999"

    def test_set_does_not_persist_without_save(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        s.set("ALLOWED_USER_ID", "999")
        # Fresh instance should read unchanged file
        s2 = Settings()
        assert s2.get("ALLOWED_USER_ID") is None

    def test_save_persists_to_disk(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        s.set("ALLOWED_USER_ID", "777")
        s.save()
        s2 = Settings()
        assert s2.get("ALLOWED_USER_ID") == "777"

    def test_save_produces_valid_json(self, config_file):
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        s.set("KEY", "VALUE")
        s.save()
        data = json.loads(config_file.read_text())
        assert data["KEY"] == "VALUE"

    def test_save_preserves_existing_keys(self, config_file):
        config_file.write_text(
            json.dumps({"BOT_TOKEN": "abc", "LOG_LEVEL": "DEBUG"}), encoding="utf-8"
        )
        s = Settings()
        s.set("ALLOWED_USER_ID", "123")
        s.save()
        data = json.loads(config_file.read_text())
        assert data["BOT_TOKEN"] == "abc"
        assert data["LOG_LEVEL"] == "DEBUG"
        assert data["ALLOWED_USER_ID"] == "123"

    def test_reload_picks_up_file_changes(self, config_file):
        config_file.write_text(json.dumps({"BOT_TOKEN": "old"}), encoding="utf-8")
        s = Settings()
        assert s.get("BOT_TOKEN") == "old"
        config_file.write_text(json.dumps({"BOT_TOKEN": "new"}), encoding="utf-8")
        s.reload()
        assert s.get("BOT_TOKEN") == "new"

    def test_full_onboarding_flow(self, config_file):
        """Simulate complete onboarding: start empty → register → reload → normal mode."""
        config_file.write_text("{}", encoding="utf-8")
        s = Settings()
        assert s.is_onboarding_mode() is True

        s.set("ALLOWED_USER_ID", "42")
        s.save()
        s.reload()

        assert s.is_onboarding_mode() is False
        assert s.get("ALLOWED_USER_ID") == "42"
