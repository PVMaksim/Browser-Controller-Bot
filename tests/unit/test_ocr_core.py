# tests/unit/test_ocr_core.py
"""
Unit tests for OCR module.
EasyOCR полностью мокируется — тесты не требуют GPU, моделей или изображений.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from src.ocr.core import OCRProcessor, clean_ocr_text, process_image_search
from src.config.settings import Settings


# ─── fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def settings():
    s = MagicMock(spec=Settings)
    s.get.side_effect = lambda key, default=None: {
        "SEARCH_ENGINE": "google",
    }.get(key, default)
    return s


@pytest.fixture
def processor(settings):
    return OCRProcessor(settings=settings)


@pytest.fixture
def fake_image(tmp_path) -> Path:
    """A real file (content doesn't matter — EasyOCR is mocked)."""
    p = tmp_path / "test.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # Minimal JPEG header
    return p


# ─── OCRProcessor.is_available ─────────────────────────────────────

class TestIsAvailable:

    def test_returns_true_when_easyocr_installed(self, processor):
        with patch("src.ocr.core.importlib.util.find_spec", return_value=MagicMock()):
            assert processor.is_available() is True

    def test_returns_false_when_easyocr_missing(self, processor):
        with patch("src.ocr.core.importlib.util.find_spec", return_value=None):
            assert processor.is_available() is False

    def test_returns_false_on_import_error(self, processor):
        with patch("src.ocr.core.importlib.util.find_spec", side_effect=Exception):
            assert processor.is_available() is False


# ─── OCRProcessor.extract_text ─────────────────────────────────────

class TestExtractText:

    def _make_reader(self, results):
        reader = MagicMock()
        reader.readtext.return_value = results
        return reader

    def test_returns_text_above_confidence(self, processor, fake_image):
        mock_reader = self._make_reader([
            (None, "Интерстеллар", 0.92),
            (None, "2014", 0.85),
        ])
        with patch.object(processor, "_get_reader", return_value=mock_reader):
            result = processor.extract_text(fake_image)
        assert result == "Интерстеллар 2014"

    def test_filters_low_confidence_segments(self, processor, fake_image):
        mock_reader = self._make_reader([
            (None, "Хорошее слово", 0.90),
            (None, "мусор###",      0.15),  # ниже порога — должно быть отброшено
        ])
        with patch.object(processor, "_get_reader", return_value=mock_reader):
            result = processor.extract_text(fake_image)
        assert result == "Хорошее слово"
        assert "мусор" not in (result or "")

    def test_returns_none_when_no_results(self, processor, fake_image):
        mock_reader = self._make_reader([])
        with patch.object(processor, "_get_reader", return_value=mock_reader):
            result = processor.extract_text(fake_image)
        assert result is None

    def test_returns_none_when_all_low_confidence(self, processor, fake_image):
        mock_reader = self._make_reader([
            (None, "abc", 0.1),
            (None, "xyz", 0.2),
        ])
        with patch.object(processor, "_get_reader", return_value=mock_reader):
            result = processor.extract_text(fake_image)
        assert result is None

    def test_filters_empty_strings(self, processor, fake_image):
        mock_reader = self._make_reader([
            (None, "   ", 0.95),   # только пробелы
            (None, "Дюна", 0.88),
        ])
        with patch.object(processor, "_get_reader", return_value=mock_reader):
            result = processor.extract_text(fake_image)
        assert result == "Дюна"


# ─── OCRProcessor._get_reader lazy loading ─────────────────────────

class TestLazyLoading:

    def test_reader_is_none_before_first_call(self, processor):
        assert processor._reader is None

    def test_reader_cached_after_first_call(self, processor, fake_image):
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = []
        mock_easyocr = MagicMock()
        mock_easyocr.Reader.return_value = mock_reader

        with patch.dict("sys.modules", {"easyocr": mock_easyocr}), \
             patch("src.ocr.core.importlib.util.find_spec", return_value=MagicMock()), \
             patch("src.ocr.core.get_cache_dir", return_value=Path("/tmp/test_cache")):
            processor.extract_text(fake_image)
            processor.extract_text(fake_image)

        # Reader создаётся только один раз
        mock_easyocr.Reader.assert_called_once()

    def test_raises_if_easyocr_not_installed(self, processor, fake_image):
        with patch("src.ocr.core.importlib.util.find_spec", return_value=None):
            # _get_reader() бросит RuntimeError
            with pytest.raises(RuntimeError, match="EasyOCR not installed"):
                processor._get_reader()


# ─── process_image_search ──────────────────────────────────────────

class TestProcessImageSearch:

    def test_returns_google_search_url(self, fake_image, settings):
        proc = OCRProcessor(settings=settings)
        with patch.object(proc, "is_available", return_value=True), \
             patch.object(proc, "extract_text", return_value="Интерстеллар 2014"):
            result = process_image_search(fake_image, settings, processor=proc)
        assert result is not None
        assert "google.com" in result
        assert "%D0%98%D0%BD" in result  # URL-encoded "Ин"

    def test_returns_none_when_no_text(self, fake_image, settings):
        proc = OCRProcessor(settings=settings)
        with patch.object(proc, "is_available", return_value=True), \
             patch.object(proc, "extract_text", return_value=None):
            result = process_image_search(fake_image, settings, processor=proc)
        assert result is None

    def test_returns_none_when_easyocr_unavailable(self, fake_image, settings):
        proc = OCRProcessor(settings=settings)
        with patch.object(proc, "is_available", return_value=False):
            result = process_image_search(fake_image, settings, processor=proc)
        assert result is None

    def test_returns_none_on_extraction_exception(self, fake_image, settings):
        proc = OCRProcessor(settings=settings)
        with patch.object(proc, "is_available", return_value=True), \
             patch.object(proc, "extract_text", side_effect=RuntimeError("GPU error")):
            result = process_image_search(fake_image, settings, processor=proc)
        assert result is None

    def test_uses_duckduckgo_when_configured(self, fake_image):
        s = MagicMock(spec=Settings)
        s.get.side_effect = lambda key, default=None: {
            "SEARCH_ENGINE": "duckduckgo",
        }.get(key, default)
        proc = OCRProcessor(settings=s)
        with patch.object(proc, "is_available", return_value=True), \
             patch.object(proc, "extract_text", return_value="test query"):
            result = process_image_search(fake_image, s, processor=proc)
        assert result is not None
        assert "duckduckgo.com" in result

    def test_creates_processor_if_none_given(self, fake_image, settings):
        """process_image_search создаёт процессор сам если не передан."""
        with patch("src.ocr.core.OCRProcessor") as MockProc:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = False
            MockProc.return_value = mock_instance
            process_image_search(fake_image, settings, processor=None)
            MockProc.assert_called_once_with(settings=settings)


# ─── clean_ocr_text ────────────────────────────────────────────────

class TestCleanOcrText:

    def test_removes_extra_spaces(self):
        assert clean_ocr_text("hello   world") == "hello world"

    def test_removes_leading_trailing_whitespace(self):
        assert clean_ocr_text("  текст  ") == "текст"

    def test_collapses_multiple_blank_lines(self):
        result = clean_ocr_text("line1\n\n\n\nline2")
        assert "\n\n\n" not in result

    def test_preserves_single_newlines(self):
        result = clean_ocr_text("line1\nline2")
        assert "line1" in result and "line2" in result

    def test_handles_empty_string(self):
        assert clean_ocr_text("") == ""

    def test_handles_only_spaces(self):
        assert clean_ocr_text("   \t  ") == ""
