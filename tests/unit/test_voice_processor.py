# tests/unit/test_voice_processor.py
"""
Tests for VoiceProcessor.
Критический инвариант: временные файлы удаляются ВСЕГДА —
и при успешной обработке, и при любой ошибке на любом этапе пайплайна.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.voice.processor import VoiceProcessor


@pytest.fixture
def processor(tmp_path, mock_settings):
    """VoiceProcessor with isolated tmp directory."""
    return VoiceProcessor(settings=mock_settings, tmp_dir=tmp_path)


@pytest.fixture
def mock_bot():
    """Mock aiogram Bot with async file methods."""
    bot = AsyncMock()
    bot.get_file = AsyncMock(return_value=MagicMock(file_path="voice/test.ogg"))
    bot.download_file = AsyncMock()
    return bot


class TestTempFileCleanup:
    """
    Ключевой инвариант: tmp-файлы удаляются через finally — всегда.
    Тесты проверяют каждый возможный сценарий отказа.
    """

    @pytest.mark.asyncio
    async def test_cleanup_after_success(self, processor, mock_bot, tmp_path):
        """Файлы удаляются после успешной обработки."""
        with patch.object(processor, "_convert_to_wav"), \
             patch.object(processor, "_transcribe", return_value="открой ютуб"):
            await processor.process(bot=mock_bot, file_id="test_file_id")

        remaining = list(tmp_path.glob("voice_*"))
        assert remaining == [], f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_cleanup_after_download_failure(self, processor, mock_bot, tmp_path):
        """Файлы удаляются если download упал."""
        mock_bot.get_file.side_effect = Exception("Telegram API error")
        result = await processor.process(bot=mock_bot, file_id="bad_id")
        assert result is None
        remaining = list(tmp_path.glob("voice_*"))
        assert remaining == [], f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_cleanup_after_ffmpeg_failure(self, processor, mock_bot, tmp_path):
        """Файлы удаляются если ffmpeg упал."""
        with patch.object(processor, "_convert_to_wav",
                          side_effect=RuntimeError("ffmpeg not found")):
            result = await processor.process(bot=mock_bot, file_id="test_id")
        assert result is None
        remaining = list(tmp_path.glob("voice_*"))
        assert remaining == [], f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_cleanup_after_whisper_failure(self, processor, mock_bot, tmp_path):
        """Файлы удаляются если Whisper упал."""
        with patch.object(processor, "_convert_to_wav"), \
             patch.object(processor, "_transcribe",
                          side_effect=RuntimeError("CUDA out of memory")):
            result = await processor.process(bot=mock_bot, file_id="test_id")
        assert result is None
        remaining = list(tmp_path.glob("voice_*"))
        assert remaining == [], f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_process_returns_none_on_any_error(self, processor, mock_bot):
        """process() никогда не бросает исключение — всегда возвращает None при ошибке."""
        mock_bot.get_file.side_effect = Exception("Любая ошибка")
        result = await processor.process(bot=mock_bot, file_id="test_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_returns_transcribed_text(self, processor, mock_bot):
        """При успехе возвращает результат транскрипции."""
        processor._download = AsyncMock()  # bypass real download
        with patch.object(processor, "_convert_to_wav"), \
             patch.object(processor, "_transcribe", return_value="открой ютуб"):
            result = await processor.process(bot=mock_bot, file_id="test_id")
        assert result == "открой ютуб"

    @pytest.mark.asyncio
    async def test_each_call_uses_unique_filename(self, processor, mock_bot):
        """Параллельные вызовы не конфликтуют по именам файлов."""
        processor._download = AsyncMock()  # bypass real download
        with patch.object(processor, "_convert_to_wav"), \
             patch.object(processor, "_transcribe", return_value="тест"):
            r1 = await processor.process(bot=mock_bot, file_id="id1")
            r2 = await processor.process(bot=mock_bot, file_id="id2")
        assert r1 == "тест"
        assert r2 == "тест"


class TestFfmpegConversion:

    def test_ffmpeg_called_with_correct_args(self, processor, tmp_path):
        """ffmpeg вызывается с параметрами 16kHz mono WAV."""
        src = tmp_path / "input.ogg"
        dst = tmp_path / "output.wav"
        src.write_bytes(b"fake ogg")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            processor._convert_to_wav(src, dst)
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-ar" in args
        assert "16000" in args
        assert "-ac" in args
        assert "1" in args

    def test_ffmpeg_nonzero_exit_raises(self, processor, tmp_path):
        """RuntimeError если ffmpeg вернул ненулевой код."""
        src = tmp_path / "input.ogg"
        dst = tmp_path / "output.wav"
        src.write_bytes(b"fake")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="No such file")
            with pytest.raises(RuntimeError, match="ffmpeg conversion failed"):
                processor._convert_to_wav(src, dst)


class TestWhisperModelLoading:

    def test_model_loaded_lazily(self, processor):
        """Модель Whisper не загружается при создании VoiceProcessor."""
        assert processor._model is None

    def test_model_cached_after_first_call(self, processor):
        """После первой загрузки модель не создаётся повторно."""
        mock_model = MagicMock()
        processor._model = mock_model
        assert processor._get_model() is mock_model

    def test_unknown_model_falls_back_to_base(self, processor, mock_settings):
        """Неизвестное имя модели → fallback на 'base'."""
        mock_settings.get.side_effect = lambda key, default=None: (
            "unknown_model_xyz" if key == "WHISPER_MODEL" else default
        )
        with patch("src.voice.processor.WhisperModel") as MockModel:
            MockModel.return_value = MagicMock()
            processor._get_model()
            call_args = MockModel.call_args[0][0]
            assert call_args == "base"
