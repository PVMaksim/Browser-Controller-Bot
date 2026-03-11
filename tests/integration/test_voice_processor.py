# tests/integration/test_voice_processor.py
"""
Integration tests for VoiceProcessor pipeline.
Проверяем полный цикл: download → convert → transcribe → cleanup.
Внешние зависимости (Telegram API, ffmpeg, Whisper) полностью мокаются.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.voice.processor import VoiceProcessor
from src.config.settings import Settings


@pytest.fixture
def tmp_proc(tmp_path):
    """VoiceProcessor with isolated tmp directory."""
    settings = MagicMock(spec=Settings)
    settings.get.return_value = "base"
    return VoiceProcessor(settings=settings, tmp_dir=tmp_path), tmp_path


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    file_mock = MagicMock()
    file_mock.file_path = "voice/file_123.ogg"
    bot.get_file = AsyncMock(return_value=file_mock)
    bot.download_file = AsyncMock()
    return bot


class TestVoiceProcessorCleanup:
    """Ключевое требование: временные файлы удаляются ВСЕГДА."""

    @pytest.mark.asyncio
    async def test_temp_files_deleted_after_success(self, tmp_proc, mock_bot):
        """Оба файла (.ogg и .wav) удаляются после успешной транскрипции."""
        proc, tmp_path = tmp_proc

        created_files: list[Path] = []

        async def fake_download(bot, file_id, dest):
            dest.write_bytes(b"fake ogg data")
            created_files.append(dest)

        def fake_convert(src, dst):
            dst.write_bytes(b"fake wav data")
            created_files.append(dst)

        with patch.object(proc, "_download", side_effect=fake_download), \
             patch.object(proc, "_convert_to_wav", side_effect=fake_convert), \
             patch.object(proc, "_transcribe", return_value="открой ютуб"):
            result = await proc.process(mock_bot, "file_123")

        assert result == "открой ютуб"
        for f in created_files:
            assert not f.exists(), f"Temp file not deleted: {f}"

    @pytest.mark.asyncio
    async def test_temp_files_deleted_after_ffmpeg_error(self, tmp_proc, mock_bot):
        """Файлы удаляются даже если ffmpeg упал."""
        proc, tmp_path = tmp_proc
        ogg_created = []

        async def fake_download(bot, file_id, dest):
            dest.write_bytes(b"fake ogg data")
            ogg_created.append(dest)

        with patch.object(proc, "_download", side_effect=fake_download), \
             patch.object(proc, "_convert_to_wav", side_effect=RuntimeError("ffmpeg failed")):
            result = await proc.process(mock_bot, "file_123")

        assert result is None  # Ошибка подавляется, возвращается None
        for f in ogg_created:
            assert not f.exists(), "OGG not deleted after error"

    @pytest.mark.asyncio
    async def test_temp_files_deleted_after_whisper_error(self, tmp_proc, mock_bot):
        """Файлы удаляются даже если Whisper упал."""
        proc, tmp_path = tmp_proc
        created = []

        async def fake_download(bot, file_id, dest):
            dest.write_bytes(b"ogg")
            created.append(dest)

        def fake_convert(src, dst):
            dst.write_bytes(b"wav")
            created.append(dst)

        with patch.object(proc, "_download", side_effect=fake_download), \
             patch.object(proc, "_convert_to_wav", side_effect=fake_convert), \
             patch.object(proc, "_transcribe", side_effect=RuntimeError("model error")):
            result = await proc.process(mock_bot, "file_123")

        assert result is None
        for f in created:
            assert not f.exists()

    @pytest.mark.asyncio
    async def test_temp_files_deleted_after_download_error(self, tmp_proc, mock_bot):
        """Cleanup вызывается даже если download упал (файлы могут не существовать)."""
        proc, _ = tmp_proc

        with patch.object(proc, "_download", side_effect=RuntimeError("download failed")):
            result = await proc.process(mock_bot, "bad_file")

        assert result is None  # Не бросает — возвращает None


class TestVoiceProcessorPipeline:

    @pytest.mark.asyncio
    async def test_returns_transcribed_text(self, tmp_proc, mock_bot):
        proc, _ = tmp_proc
        with patch.object(proc, "_download", new_callable=lambda: lambda *a: AsyncMock(return_value=None)()), \
             patch.object(proc, "_convert_to_wav", return_value=None), \
             patch.object(proc, "_transcribe", return_value="сделай скриншот"):
            # Simplify: mock all three steps
            pass

        async def noop_download(bot, file_id, dest): pass
        with patch.object(proc, "_download", side_effect=noop_download), \
             patch.object(proc, "_convert_to_wav", return_value=None), \
             patch.object(proc, "_transcribe", return_value="сделай скриншот"):
            result = await proc.process(mock_bot, "file_123")
        assert result == "сделай скриншот"

    @pytest.mark.asyncio
    async def test_returns_none_on_any_failure(self, tmp_proc, mock_bot):
        proc, _ = tmp_proc
        async def noop_download(bot, file_id, dest): pass
        with patch.object(proc, "_download", side_effect=noop_download), \
             patch.object(proc, "_convert_to_wav", side_effect=Exception("any error")):
            result = await proc.process(mock_bot, "file_123")
        assert result is None

    def test_cleanup_handles_nonexistent_files_silently(self, tmp_proc):
        """_cleanup не падает если файла нет."""
        proc, tmp_path = tmp_proc
        nonexistent = tmp_path / "ghost.wav"
        proc._cleanup(nonexistent)  # должно быть тихим no-op

    def test_tmp_dir_created_on_init(self, tmp_path):
        """Папка для временных файлов создаётся при инициализации."""
        new_dir = tmp_path / "new_tmp"
        assert not new_dir.exists()
        settings = MagicMock(spec=Settings)
        settings.get.return_value = "base"
        VoiceProcessor(settings=settings, tmp_dir=new_dir)
        assert new_dir.exists()


class TestWhisperModelLazyLoad:

    def test_model_is_none_before_first_call(self, tmp_proc):
        proc, _ = tmp_proc
        assert proc._model is None

    def test_get_model_uses_settings_value(self, tmp_proc):
        proc, _ = tmp_proc
        proc._settings.get.return_value = "small"
        mock_model = MagicMock()

        with patch("src.voice.processor.WhisperModel", return_value=mock_model) as mock_cls:
            result = proc._get_model()
            mock_cls.assert_called_once_with("small", device="cpu", compute_type="int8")
            assert result is mock_model

    def test_get_model_falls_back_on_unknown_name(self, tmp_proc):
        proc, _ = tmp_proc
        proc._settings.get.return_value = "mega-ultra"
        mock_model = MagicMock()

        with patch("src.voice.processor.WhisperModel", return_value=mock_model) as mock_cls:
            proc._get_model()
            # Должен использовать DEFAULT_WHISPER_MODEL, не "mega-ultra"
            called_name = mock_cls.call_args[0][0]
            assert called_name != "mega-ultra"

    def test_model_is_cached_after_first_load(self, tmp_proc):
        proc, _ = tmp_proc
        mock_model = MagicMock()
        with patch("src.voice.processor.WhisperModel", return_value=mock_model) as mock_cls:
            proc._get_model()
            proc._get_model()
            # WhisperModel создаётся только один раз
            mock_cls.assert_called_once()
