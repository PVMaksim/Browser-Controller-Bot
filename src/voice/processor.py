# src/voice/processor.py
"""
Voice message processing pipeline:
  1. Download .ogg file from Telegram to tmp/
  2. Convert .ogg → .wav via ffmpeg (required by faster-whisper)
  3. Transcribe .wav with faster-whisper (offline, local)
  4. Delete ALL temp files in finally — guaranteed, even on error

Все временные файлы удаляются через finally — гарантированно.
Голосовые данные никогда не отправляются за пределы устройства.
"""

import subprocess
import uuid
from pathlib import Path

from aiogram import Bot
from loguru import logger

from src.config.constants import (
    DEFAULT_WHISPER_MODEL,
    VOICE_TMP_PREFIX,
    VOICE_TMP_SUFFIX,
    WHISPER_SUPPORTED_MODELS,
)
from src.config.paths import get_voice_tmp_dir

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore
from src.config.settings import Settings


class VoiceProcessor:
    """
    Processes Telegram voice messages end-to-end.
    Создаётся один раз при старте бота и переиспользуется для всех сообщений.
    Модель Whisper загружается лениво при первом вызове.
    """

    def __init__(self, settings: Settings, tmp_dir: Path | None = None) -> None:
        self._settings = settings
        self._tmp_dir: Path = tmp_dir or get_voice_tmp_dir()
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        # Lazy-loaded Whisper model — инициализируется при первом вызове process()
        self._model = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def process(self, bot: Bot, file_id: str) -> str | None:
        """
        Download voice file from Telegram, transcribe, clean up.
        Возвращает распознанный текст или None если транскрипция не удалась.

        Временные файлы (.ogg и .wav) гарантированно удаляются через finally,
        даже если на любом этапе возникнет исключение.
        """
        uid = uuid.uuid4().hex[:8]
        ogg_path = self._tmp_dir / f"{VOICE_TMP_PREFIX}{uid}.ogg"
        wav_path = self._tmp_dir / f"{VOICE_TMP_PREFIX}{uid}{VOICE_TMP_SUFFIX}"

        try:
            # Шаг 1: скачиваем файл из Telegram
            await self._download(bot, file_id, ogg_path)

            # Шаг 2: конвертируем .ogg → .wav
            self._convert_to_wav(ogg_path, wav_path)

            # Шаг 3: транскрибируем
            text = self._transcribe(wav_path)
            logger.info(f"Transcribed voice [{uid}]: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Voice processing failed [{uid}]: {e}")
            return None

        finally:
            # Гарантированное удаление — выполняется всегда, даже при исключении
            self._cleanup(ogg_path, wav_path)

    # ------------------------------------------------------------------ #
    # Internal steps                                                       #
    # ------------------------------------------------------------------ #

    async def _download(self, bot: Bot, file_id: str, dest: Path) -> None:
        """Download voice file from Telegram servers to local path."""
        file = await bot.get_file(file_id)
        if not file.file_path:
            raise ValueError(f"Empty file_path for file_id={file_id}")
        await bot.download_file(file.file_path, destination=str(dest))
        logger.debug(f"Downloaded voice file: {dest} ({dest.stat().st_size} bytes)")

    def _convert_to_wav(self, src: Path, dst: Path) -> None:
        """
        Convert audio to 16kHz mono WAV using ffmpeg.
        faster-whisper требует WAV 16kHz mono для корректной транскрипции.
        """
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",               # Перезаписать если файл существует
                "-i", str(src),
                "-ar", "16000",     # 16 kHz — требование Whisper
                "-ac", "1",         # Mono
                "-f", "wav",
                str(dst),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg conversion failed (code {result.returncode}): {result.stderr[:300]}"
            )
        logger.debug(f"Converted {src.name} → {dst.name}")

    def _transcribe(self, wav_path: Path) -> str:
        """
        Transcribe WAV file using faster-whisper (offline, local).
        Модель загружается в память при первом вызове и кэшируется.
        Поддерживает русский язык без явного указания — авто-определение.
        """
        model = self._get_model()
        segments, info = model.transcribe(
            str(wav_path),
            beam_size=5,
            language=None,          # Авто-определение языка
            vad_filter=True,        # Фильтр тишины — игнорируем паузы
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        logger.debug(f"Whisper detected language: {info.language}, prob: {info.language_probability:.2f}")
        return text

    def _get_model(self):
        """
        Lazy-load Whisper model on first call.
        Загрузка занимает несколько секунд — делаем один раз при первом голосовом сообщении.
        """
        if self._model is None:
            model_name = self._settings.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL)
            if model_name not in WHISPER_SUPPORTED_MODELS:
                logger.warning(
                    f"Unknown Whisper model '{model_name}', falling back to 'base'"
                )
                model_name = DEFAULT_WHISPER_MODEL

            logger.info(f"Loading Whisper model: {model_name} (first voice message)")
            from faster_whisper import WhisperModel

            # cpu + int8 — оптимально для Mac без GPU; float16 требует CUDA
            self._model = WhisperModel(model_name, device="cpu", compute_type="int8")
            logger.info(f"Whisper model '{model_name}' loaded")
        return self._model

    @staticmethod
    def _cleanup(*paths: Path) -> None:
        """Delete temp files silently. Called in finally — must never raise."""
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
                    logger.debug(f"Cleaned up temp file: {path.name}")
            except Exception as e:
                # Логируем но не бросаем — finally не должен маскировать исходную ошибку
                logger.warning(f"Failed to delete temp file {path}: {e}")
