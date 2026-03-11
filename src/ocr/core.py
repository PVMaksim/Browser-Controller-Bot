# src/ocr/core.py
"""
OCR module — Stage 4.
Extracts text from screenshots/photos and generates a search URL.

Сценарий использования:
  1. Пользователь отправляет фото (скриншот с названием фильма, текстом с экрана и т.д.)
  2. process_image_search() распознаёт текст через EasyOCR
  3. Возвращает поисковый URL для найденного текста

EasyOCR выбран перед PaddleOCR:
  - Стабильная поддержка русского языка
  - Простая установка (pip install easyocr)
  - Модели скачиваются автоматически (~100–200 МБ при первом запуске)
  - Работает офлайн после первой загрузки моделей

Зависимости: easyocr>=1.7.0 (добавить в requirements.txt)
Размер моделей: ~130 МБ (en + ru)
"""

import importlib.util
from pathlib import Path
from urllib.parse import quote_plus

from loguru import logger

from src.config.constants import SEARCH_ENGINES, OCR_LANGUAGES, OCR_MIN_CONFIDENCE
from src.config.paths import get_cache_dir
from src.config.settings import Settings


class OCRProcessor:
    """
    Extracts text from images using EasyOCR.
    Модели Whisper и OCR используют одинаковый паттерн lazy-загрузки:
    инициализируются при первом вызове и кэшируются в памяти.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._reader = None  # lazy-loaded EasyOCR reader

    def is_available(self) -> bool:
        """Return True if EasyOCR is installed."""
        try:
            return importlib.util.find_spec("easyocr") is not None
        except Exception:
            return False

    def _get_reader(self):
        """
        Lazy-load EasyOCR reader on first call.
        Загрузка занимает 3–8 секунд — делается один раз.
        Модели сохраняются в cache dir и не скачиваются повторно.
        """
        if self._reader is not None:
            return self._reader

        if not self.is_available():
            raise RuntimeError(
                "EasyOCR not installed. Run: pip install easyocr\n"
                "После установки модели (~130 МБ) скачаются при первом запуске."
            )

        import easyocr

        # Храним модели в системном cache dir — не засоряем рабочую папку
        model_storage = get_cache_dir() / "easyocr_models"
        model_storage.mkdir(parents=True, exist_ok=True)

        languages = list(OCR_LANGUAGES)  # ["ru", "en"]

        logger.info(f"Loading EasyOCR ({'+'.join(languages)}) — first run downloads models...")
        self._reader = easyocr.Reader(
            languages,
            model_storage_directory=str(model_storage),
            gpu=False,          # CPU — совместимо с любым Mac/Windows без GPU
            verbose=False,      # Не засоряем stdout EasyOCR-логами
        )
        logger.info("EasyOCR loaded successfully")
        return self._reader

    def extract_text(self, image_path: Path) -> str | None:
        """
        Extract text from image file.
        Возвращает очищенный текст или None если текст не найден / уверенность низкая.
        """
        reader = self._get_reader()

        logger.debug(f"OCR: processing {image_path.name}")
        results = reader.readtext(str(image_path), detail=1)

        if not results:
            logger.debug("OCR: no text detected")
            return None

        # Фильтруем по минимальной уверенности и собираем текст
        confident_parts = [
            text.strip()
            for _, text, confidence in results
            if confidence >= OCR_MIN_CONFIDENCE and text.strip()
        ]

        if not confident_parts:
            logger.debug(f"OCR: all results below confidence threshold ({OCR_MIN_CONFIDENCE})")
            return None

        full_text = " ".join(confident_parts)
        logger.info(f"OCR: extracted '{full_text[:80]}...' ({len(confident_parts)} segments)")
        return full_text


def process_image_search(
    image_path: Path,
    settings: Settings,
    processor: OCRProcessor | None = None,
) -> str | None:
    """
    Extract text from screenshot and generate a search URL.
    Returns ready-to-use search URL or None if extraction fails.

    Интерфейс не изменяется при смене OCR-движка — только внутренняя реализация.
    Вызывается из хендлера фото (handlers/photo.py).

    Args:
        image_path: Path to the image file (JPEG/PNG).
        settings: Application settings (for search engine preference).
        processor: OCRProcessor instance (create once, reuse).

    Returns:
        Search URL string, or None on failure.
    """
    if processor is None:
        processor = OCRProcessor(settings=settings)

    if not processor.is_available():
        logger.warning("OCR: EasyOCR not available — install with: pip install easyocr")
        return None

    try:
        text = processor.extract_text(image_path)
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return None

    if not text:
        return None

    # Выбираем поисковую систему из настроек
    engine = settings.get("SEARCH_ENGINE", "google").lower()
    base_url = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
    search_url = base_url + quote_plus(text)

    logger.info(f"OCR search URL: {search_url[:80]}...")
    return search_url


def clean_ocr_text(raw_text: str) -> str:
    """
    Normalize raw OCR output for display in Telegram message.
    Убирает лишние пробелы, нормализует переносы строк.
    """
    import re
    # Убираем повторяющиеся пробелы и пустые строки
    text = re.sub(r"[ \t]+", " ", raw_text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
