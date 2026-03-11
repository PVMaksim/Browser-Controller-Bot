# src/handlers/photo.py
"""
Photo message handler — Stage 4.
Получает фото от пользователя → скачивает → OCR → возвращает поисковую ссылку.

Сценарии использования:
  - Скриншот с названием фильма/сериала → поиск на RuTube/YouTube
  - Фото с вывески, меню, книги → поиск по тексту в браузере
  - Скриншот экрана телефона с текстом → любой запрос

Временный файл фото удаляется через finally — гарантированно.
"""

import uuid
from pathlib import Path

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message, PhotoSize
from loguru import logger

from src.config.constants import OCR_MAX_IMAGE_BYTES
from src.config.paths import get_ocr_tmp_dir
from src.config.settings import Settings
from src.middlewares.access_control import check_access
from src.ocr.core import OCRProcessor, clean_ocr_text, process_image_search


def get_photo_router(settings: Settings, bot: Bot, ocr_processor=None) -> Router:
    """
    Build photo handler router.
    OCRProcessor можно передать снаружи (создан в main.py) — модели не перегружаются.
    Если не передан — создаётся здесь.
    """
    r = Router()
    if ocr_processor is None:
        ocr_processor = OCRProcessor(settings=settings)

    # Один раз предупреждаем при старте если EasyOCR не установлен
    if not ocr_processor.is_available():
        logger.warning(
            "EasyOCR not installed — photo OCR disabled. "
            "Install: pip install easyocr"
        )

    async def _guard(message: Message) -> bool:
        if not message.from_user:
            return False
        return await check_access(message.from_user.id, bot, settings)

    @r.message(lambda m: m.photo is not None and len(m.photo) > 0)
    async def handle_photo(message: Message) -> None:
        """
        Process incoming photo: download → OCR → reply with search link.
        Пользователь отправляет фото — бот распознаёт текст и возвращает поисковую ссылку.
        """
        if not await _guard(message):
            return

        # EasyOCR не установлен — сообщаем пользователю
        if not ocr_processor.is_available():
            await message.answer(
                "📷 <b>OCR недоступен</b>\n\n"
                "Для распознавания текста на фото нужен EasyOCR.\n"
                "Установи: <code>pip install easyocr</code>\n\n"
                "После установки модели (~130 МБ) скачаются автоматически."
            )
            return

        # Берём фото наибольшего размера (последнее в массиве)
        best_photo: PhotoSize = message.photo[-1]

        # Проверяем размер файла
        if best_photo.file_size and best_photo.file_size > OCR_MAX_IMAGE_BYTES:
            await message.answer(
                f"⚠️ Файл слишком большой ({best_photo.file_size // 1024 // 1024} МБ). "
                f"Максимум: {OCR_MAX_IMAGE_BYTES // 1024 // 1024} МБ."
            )
            return

        # Показываем индикатор обработки — OCR занимает 1–5 секунд
        processing_msg = await message.answer("🔍 Распознаю текст...")

        tmp_path: Path | None = None
        try:
            # Скачиваем фото во временный файл
            uid = uuid.uuid4().hex[:8]
            tmp_path = get_ocr_tmp_dir() / f"ocr_{uid}.jpg"

            file_info = await bot.get_file(best_photo.file_id)
            if not file_info.file_path:
                raise ValueError("Empty file_path from Telegram API")

            await bot.download_file(file_info.file_path, destination=str(tmp_path))
            logger.info(f"OCR photo downloaded: {tmp_path} ({tmp_path.stat().st_size:,} bytes)")

            # Запускаем OCR
            search_url = process_image_search(
                image_path=tmp_path,
                settings=settings,
                processor=ocr_processor,
            )

            # Также получаем чистый текст для отображения пользователю
            raw_text = ocr_processor.extract_text(tmp_path)

        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            await processing_msg.delete()
            await message.answer(
                "❌ <b>Ошибка распознавания</b>\n\n"
                f"<code>{str(e)[:200]}</code>"
            )
            return

        finally:
            # Гарантированное удаление временного файла
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                    logger.debug(f"OCR temp file deleted: {tmp_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete OCR temp file: {e}")

        # Удаляем «Распознаю текст...» и отвечаем результатом
        await processing_msg.delete()

        if not search_url or not raw_text:
            await message.answer(
                "🔍 <b>Текст не распознан</b>\n\n"
                "На фото не удалось найти достаточно чёткого текста.\n"
                "Попробуй более качественное изображение."
            )
            return

        display_text = clean_ocr_text(raw_text)
        # Обрезаем до разумного размера для сообщения
        if len(display_text) > 300:
            display_text = display_text[:297] + "..."

        engine_name = settings.get("SEARCH_ENGINE", "google").capitalize()

        await message.answer(
            f"📷 <b>Распознанный текст:</b>\n"
            f"<code>{display_text}</code>\n\n"
            f"🔍 <a href='{search_url}'>Искать в {engine_name}</a>",
            disable_web_page_preview=True,
        )
        logger.info(f"OCR result sent to user: '{display_text[:50]}'")

    @r.message(Command("ocr"))
    async def cmd_ocr_help(message: Message) -> None:
        """Show OCR usage hint."""
        if not await _guard(message):
            return

        status = "✅ активен" if ocr_processor.is_available() else "❌ не установлен (pip install easyocr)"
        await message.answer(
            "📷 <b>OCR — распознавание текста на фото</b>\n\n"
            f"Статус: {status}\n\n"
            "Просто отправь фото — бот распознает текст и откроет поиск.\n\n"
            "<b>Примеры:</b>\n"
            "• Скриншот с названием фильма → поиск на RuTube\n"
            "• Фото книжной обложки → поиск в браузере\n"
            "• Скриншот с текстом → поиск по словам\n\n"
            "<i>Поддерживаемые языки: русский, английский</i>"
        )

    return r
