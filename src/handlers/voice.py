# src/handlers/voice.py
"""
Telegram voice message handler.
Транскрипция → маппинг → исполнение команды (браузер / плеер / система).
"""

from aiogram import Bot, Router
from aiogram.types import BufferedInputFile, Message
from loguru import logger

from src.browser.engine import BrowserEngine
from src.browser.idle_watcher import IdleWatcher
from src.config.settings import Settings
from src.core.command_parser import ParsedCommand
from src.middlewares.access_control import check_access
from src.player.controller import PlayerController
from src.utils.sanitize import sanitize_caption
from src.utils.validators import normalize_url, sanitize_search_query, validate_url
from src.voice.command_mapper import VoiceCommandMapper
from src.voice.processor import VoiceProcessor


def get_voice_router(
    settings: Settings,
    bot: Bot,
    browser: BrowserEngine,
    idle_watcher: IdleWatcher,
    voice_processor: VoiceProcessor,
    player: PlayerController,
) -> Router:
    """Build voice message router wired to all dependencies."""
    r = Router()
    mapper = VoiceCommandMapper()

    @r.message(lambda msg: msg.voice is not None or msg.audio is not None)
    async def handle_voice(message: Message) -> None:
        """Transcribe voice → map command → execute."""
        if not message.from_user:
            return
        if not await check_access(message.from_user.id, bot, settings):
            await message.answer("⛔ Доступ запрещён.")
            return

        file_id = message.voice.file_id if message.voice else message.audio.file_id  # type: ignore

        status_msg = await message.answer("🎙 Распознаю голос...")
        text = await voice_processor.process(bot=bot, file_id=file_id)

        if not text:
            await status_msg.edit_text(
                "❓ Не удалось распознать речь.\n"
                "Попробуй ещё раз или напиши команду текстом."
            )
            return

        await status_msg.edit_text(f"🎙 Распознано: <i>{text}</i>\n⏳ Выполняю...")

        command = mapper.map(text)
        if not command:
            await status_msg.edit_text(
                f"🎙 Распознано: <i>{text}</i>\n\n"
                "❓ Команда не распознана.\n"
                "Скажи: «открой ютуб», «поставь на паузу», «найди фильм Дюна на рутубе»"
            )
            return

        result_text = await _execute_command(
            command=command,
            message=message,
            bot=bot,
            browser=browser,
            idle_watcher=idle_watcher,
            player=player,
            settings=settings,
        )
        await status_msg.edit_text(f"🎙 <i>{text}</i>\n\n{result_text}")

    return r


async def _execute_command(
    command: ParsedCommand,
    message: Message,
    bot: Bot,
    browser: BrowserEngine,
    idle_watcher: IdleWatcher,
    player: PlayerController,
    settings: Settings,
) -> str:
    """Execute parsed command. Returns result string. Never raises."""
    cmd = command.command
    arg = command.argument or ""

    try:
        # ---- Навигация ----
        if cmd == "open":
            url = normalize_url(arg) if arg else ""
            if not url or not validate_url(url):
                return f"❌ Не удалось определить URL из: «{arg}»"
            await browser.open_url(url)
            idle_watcher.reset()
            return f"✅ Открыто: <code>{url}</code>"

        elif cmd == "search":
            query = sanitize_search_query(arg)
            if not query:
                return "❌ Не удалось извлечь поисковый запрос."
            await browser.search(query)
            idle_watcher.reset()
            return f"✅ Поиск: <i>{query}</i>"

        elif cmd == "shot":
            if not browser.is_running:
                return "ℹ️ Браузер не запущен."
            png_bytes = await browser.take_screenshot()
            idle_watcher.reset()
            current_url = browser.get_current_url() or "—"
            await message.answer_photo(
                photo=BufferedInputFile(png_bytes, filename="screenshot.png"),
                caption=sanitize_caption(f"📸 {current_url}"),
            )
            return "📸 Скриншот отправлен"

        elif cmd == "close":
            if not browser.is_running:
                return "ℹ️ Браузер не запущен."
            await browser.close_tab()
            idle_watcher.reset()
            return "✅ Вкладка закрыта."

        elif cmd == "status":
            from src.utils.system_info import format_status_message
            return format_status_message(current_url=browser.get_current_url())

        # ---- Медиапульт ----
        elif cmd == "find":
            # arg: "platform query" — разбираем
            parts = arg.split(maxsplit=1)
            from src.handlers.player import _PLATFORM_ALIASES
            if len(parts) == 2 and parts[0].lower() in _PLATFORM_ALIASES:
                platform = _PLATFORM_ALIASES[parts[0].lower()]
                query = parts[1]
            else:
                platform = None
                query = arg
            results = await player.search(query=query, platform=platform)
            if not results:
                return f"😔 Ничего не найдено по запросу «{query}»."
            from src.player.keyboards import build_search_results_keyboard
            from src.handlers.player import _PLATFORM_NAMES
            platform_name = _PLATFORM_NAMES.get(player.state.platform or "", "")
            keyboard = build_search_results_keyboard(results)
            await message.answer(
                f"🔍 <b>{platform_name}</b> — «{query}» — {len(results)} результатов:",
                reply_markup=keyboard,
            )
            return "👆 Выбери видео кнопкой выше."

        elif cmd == "play":
            await player.play()
            return "▶️ Воспроизведение"

        elif cmd == "pause":
            await player.pause()
            return "⏸ Пауза"

        elif cmd == "rewind":
            secs = int(arg) if arg.isdigit() else 30
            await player.seek(-secs)
            return f"⏪ −{secs}с"

        elif cmd == "forward":
            secs = int(arg) if arg.isdigit() else 30
            await player.seek(secs)
            return f"⏩ +{secs}с"

        elif cmd == "vol":
            new_vol = await player.set_volume(arg or "+20")
            return f"🔊 Громкость: {new_vol}%"

        elif cmd == "mute":
            muted = await player.toggle_mute()
            return "🔇 Звук выключен" if muted else "🔊 Звук включён"

        elif cmd == "mediastat":
            state = await player.get_current_state()
            if not state.is_active:
                return "ℹ️ Плеер не активен."
            return (
                f"📊 {state.title or '—'}\n"
                f"⏱ {state.format_position()} · 🔊 {state.volume}%"
            )

        # ---- Системные команды ----
        elif cmd == "sleep":
            from src.system.macos_commands import sleep_mac
            await sleep_mac()
            return "😴 Mac уходит в сон..."

        elif cmd == "lock":
            from src.system.macos_commands import lock_screen
            await lock_screen()
            return "🔒 Экран заблокирован."

        elif cmd == "sysinfo":
            from src.system.macos_commands import get_system_info
            info = await get_system_info()
            return info.format_telegram()

        else:
            return f"❓ Неизвестная команда: <code>{cmd}</code>"

    except Exception as e:
        logger.error(f"Voice command execution error: cmd={cmd} arg={arg!r}: {e}")
        return f"❌ Ошибка команды <code>{cmd}</code>: {str(e)[:200]}"
