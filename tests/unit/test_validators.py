# tests/unit/test_validators.py
"""
Tests for URL validation and input sanitization.
Защита от инъекций — первый и самый важный рубеж.
"""

import pytest

from src.utils.validators import normalize_url, sanitize_search_query, validate_url


class TestUrlValidator:
    """Tests for URL validation before passing to browser."""

    def test_valid_https_url(self):
        assert validate_url("https://youtube.com") is True

    def test_valid_http_url(self):
        assert validate_url("http://example.com") is True

    def test_javascript_injection_blocked(self):
        # Защита от JS-инъекций через URL
        assert validate_url("javascript:alert(1)") is False

    def test_data_scheme_blocked(self):
        assert validate_url("data:text/html,<h1>hack</h1>") is False

    def test_ftp_scheme_blocked(self):
        assert validate_url("ftp://files.example.com") is False

    def test_file_scheme_blocked(self):
        assert validate_url("file:///etc/passwd") is False

    def test_vbscript_scheme_blocked(self):
        assert validate_url("vbscript:msgbox(1)") is False

    def test_missing_scheme_blocked(self):
        # URL без схемы должен быть отклонён (нормализацию делает normalize_url)
        assert validate_url("youtube.com") is False

    def test_empty_string_blocked(self):
        assert validate_url("") is False

    def test_none_blocked(self):
        assert validate_url(None) is False  # type: ignore[arg-type]

    def test_javascript_case_insensitive(self):
        # Атака с заглавными буквами
        assert validate_url("JAVASCRIPT:alert(1)") is False
        assert validate_url("JavaScript:alert(1)") is False

    def test_data_case_insensitive(self):
        assert validate_url("DATA:text/html,hack") is False

    @pytest.mark.parametrize("url", [
        "https://google.com/search?q=test",
        "https://sub.domain.co.uk/path?key=value#anchor",
        "http://localhost:8080",
        "https://rutube.ru/video/abc123/",
        "https://vk.com/video",
    ])
    def test_complex_valid_urls(self, url: str):
        assert validate_url(url) is True


class TestNormalizeUrl:
    """Tests for URL normalization (adding https:// prefix)."""

    def test_adds_https_prefix(self):
        assert normalize_url("youtube.com") == "https://youtube.com"

    def test_does_not_double_prefix(self):
        assert normalize_url("https://youtube.com") == "https://youtube.com"

    def test_preserves_http(self):
        assert normalize_url("http://example.com") == "http://example.com"

    def test_strips_whitespace(self):
        assert normalize_url("  youtube.com  ") == "https://youtube.com"


class TestSanitizeSearchQuery:
    """Tests for search query sanitization."""

    def test_trims_whitespace(self):
        assert sanitize_search_query("  hello world  ") == "hello world"

    def test_collapses_spaces(self):
        assert sanitize_search_query("рецепт   борща") == "рецепт борща"

    def test_limits_length(self):
        long_query = "a" * 1000
        result = sanitize_search_query(long_query)
        assert len(result) <= 500

    def test_empty_string(self):
        assert sanitize_search_query("") == ""

    def test_preserves_russian(self):
        assert sanitize_search_query("рецепт борща") == "рецепт борща"
