# src/handlers/commands.py
"""
Core command handlers: /start, /open, /search, /shot, /close, /status, /stop, /help.
Этап 6: полный /help, красивый /status, inline-кнопки быстрых действий.
"""

import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from loguru import logger

from src.browser.engine import BrowserEngine
from src.browser.idle_watcher import IdleWatcher
from src.config.constants import (
    APP_VERSION,
    DEFAULT_STOP_CONFIRM_TIMEOUT_SECONDS,
    DEFAULT_WHISPER_MODEL,
    STOP_CONFIRM_SUFFIX,
)
from src.config.settings import Settings
from src.middlewares.access_control import check_access
from src.utils.sanitize import sanitize_caption
from src.utils.system_info import format_status_message
from src.utils.validators import normalize_url, sanitize_search_query, validate_url

_stop_confirmations: dict[int, datetime] = {}


def get_command_router(
    settings: Settings,
    bot: Bot,
    browser: BrowserEngine,
    idle_watcher: IdleWatcher,
    watchdog=None,       # BrowserWatchdog | None — optional to avoid circular import
    ocr_processor=None,  # OCRProcessor | None — optional
) -> Router:
    """Build and return the main command router."""
    r = Router()

    async def _guard(message: Message) -> bool:
        if not message.from_user:
            return False
        return await check_access(message.from_user.id, bot, settings)

    def _get_arg(message: Message) -> str:
        text = message.text or ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    # ------------------------------------------------------------------ #
    # /start                                                               #
    # ------------------------------------------------------------------ #

    @r.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        """Handle /start: greeting with quick-action buttons."""
        if not await _guard(message):
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📖 Помощь",    callback_data="cmd:help"),
                InlineKeyboardButton(text="📊 Статус",   callback_data="cmd:status"),
            ],
            [
                InlineKeyboardButton(text="🔍 Поиск",    callback_data="cmd:search_hint"),
                InlineKeyboardButton(text="📸 Скриншот", callback_data="cmd:shot"),
            ],
        ])
        await message.answer(
            "👋 <b>Secure Browser Bot</b> активен!\n\n"
            "Управляй браузером и медиаплеером на своём Mac прямо из Telegram.\n"
            "Поддерживает текстовые и голосовые команды.\n\n"
            "Отправь /help для полного списка команд.",
            reply_markup=keyboard,
        )

    # ------------------------------------------------------------------ #
    # /help — Этап 6: полный список с группировкой                        #
    # ------------------------------------------------------------------ #

    @r.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        """Show complete command list grouped by category."""
        if not await _guard(message):
            return

        whisper_model = settings.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL)

        help_text = (
            "📖 <b>Все команды</b>\n\n"

            "━━ 🌐 <b>Браузер</b> ━━\n"
            "/open &lt;url&gt; — открыть сайт\n"
            "/search &lt;запрос&gt; — поиск в браузере\n"
            "/shot — скриншот текущей страницы\n"
            "/close — закрыть вкладку\n\n"

            "━━ 📺 <b>Медиапульт</b> ━━\n"
            "/find [платформа] &lt;запрос&gt; — поиск видео\n"
            "   платформы: <code>рутуб</code> <code>ютуб</code> <code>вк</code> <code>ок</code>\n"
            "/play — подсказка управления плеером\n"
            "/pause — подсказка паузы\n"
            "/mediastat — статус плеера (позиция, громкость)\n"
            "/watchlist — список «Посмотреть позже»\n"
            "/wladd [url] — добавить текущее видео в список\n"
            "/wlclear — очистить список\n"
            "<i>▶️ ⏸ ⏪ ⏩ 🔇 — inline-кнопки управления под плеером</i>\n\n"

            "━━ 💻 <b>Компьютер</b> ━━\n"
            "/sleep — режим сна\n"
            "/lock — блокировка экрана\n"
            "/vol_sys &lt;0–100&gt; — системная громкость\n"
            "/mute_sys — выкл/вкл системный звук\n"
            "/sysinfo — CPU, RAM, диск, uptime\n"
            "/copy &lt;текст&gt; — скопировать текст в буфер\n\n"

            "━━ 📷 <b>OCR — текст на фото</b> ━━\n"
            "Отправь фото — бот распознает текст и откроет поиск\n"
            "   • скриншот с названием фильма → поиск\n"
            "   • фото обложки, вывески, документа → поиск\n"
            "/ocr — статус OCR и справка\n\n"

            "━━ ⚙️ <b>Управление ботом</b> ━━\n"
            "/status — версия, браузер, Whisper, watchdog, OCR\n"
            "/stop — остановить бота (требует <code>/stop confirm</code>)\n"
            "/help — эта страница\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎙 <b>Голос</b> — все команды принимаются голосовым сообщением\n"
            f"   Модель: <code>whisper-{whisper_model}</code>\n"
            f"   Примеры: «открой youtube.com», «найди котиков на рутубе»,\n"
            f"   «пауза», «погромче», «заблокируй экран»\n"
            f"⚡ <b>Rate limit</b>: не более 10 команд за 10 сек\n"
            f"<i>Задержка управления плеером 1–2 сек — норма.</i>"
        )
        await message.answer(help_text)

    # ------------------------------------------------------------------ #
    # /status — Этап 6: расширенный с моделью Whisper                    #
    # ------------------------------------------------------------------ #

    @r.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        """Show rich bot and browser status."""
        if not await _guard(message):
            return
        current_url = browser.get_current_url()
        whisper_model = settings.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL)
        watchdog_restarts = watchdog.restart_count if watchdog else None
        ocr_ok = ocr_processor.is_available() if ocr_processor else None
        await message.answer(
            format_status_message(
                current_url=current_url,
                whisper_model=whisper_model,
                version=APP_VERSION,
                watchdog_restarts=watchdog_restarts,
                ocr_available=ocr_ok,
            )
        )

    # ------------------------------------------------------------------ #
    # /open                                                                #
    # ------------------------------------------------------------------ #

    @r.message(Command("open"))
    async def cmd_open(message: Message) -> None:
        """Handle /open <url>: validate and navigate."""
        if not await _guard(message):
            return
        raw = _get_arg(message)
        if not raw:
            await message.answer(
                "❌ Укажи URL.\n\nПример: <code>/open youtube.com</code>"
            )
            return
        url = normalize_url(raw)
        if not validate_url(url):
            await message.answer(
                f"❌ Недопустимый URL: <code>{raw}</code>\n"
                "Поддерживаются только <b>http://</b> и <b>https://</b>"
            )
            logger.warning(f"Blocked invalid URL: {raw}")
            return
        await message.answer(f"🌐 Открываю: <code>{url}</code>")
        try:
            await browser.open_url(url)
            idle_watcher.reset()
        except Exception as e:
            await message.answer(f"❌ Не удалось открыть: <code>{str(e)[:200]}</code>")

    # ------------------------------------------------------------------ #
    # /search                                                              #
    # ------------------------------------------------------------------ #

    @r.message(Command("search"))
    async def cmd_search(message: Message) -> None:
        """Handle /search <query>."""
        if not await _guard(message):
            return
        raw = _get_arg(message)
        if not raw:
            await message.answer(
                "❌ Укажи запрос.\n\nПример: <code>/search рецепт борща</code>"
            )
            return
        query = sanitize_search_query(raw)
        await message.answer(f"🔍 Ищу: <i>{query}</i>")
        try:
            await browser.search(query)
            idle_watcher.reset()
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{str(e)[:200]}</code>")

    # ------------------------------------------------------------------ #
    # /shot                                                                #
    # ------------------------------------------------------------------ #

    @r.message(Command("shot"))
    async def cmd_shot(message: Message) -> None:
        """Take screenshot and send as photo."""
        if not await _guard(message):
            return
        if not browser.is_running:
            await message.answer("ℹ️ Браузер не запущен. Открой что-нибудь через /open")
            return
        await message.answer("📸 Делаю скриншот...")
        try:
            png_bytes = await browser.take_screenshot()
            idle_watcher.reset()
            current_url = browser.get_current_url() or "—"
            await message.answer_photo(
                photo=BufferedInputFile(png_bytes, filename="screenshot.png"),
                caption=sanitize_caption(f"📸 {current_url}"),
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка скриншота: <code>{str(e)[:200]}</code>")

    # ------------------------------------------------------------------ #
    # /close                                                               #
    # ------------------------------------------------------------------ #

    @r.message(Command("close"))
    async def cmd_close(message: Message) -> None:
        """Close current browser tab."""
        if not await _guard(message):
            return
        if not browser.is_running:
            await message.answer("ℹ️ Браузер не запущен.")
            return
        try:
            await browser.close_tab()
            idle_watcher.reset()
            await message.answer("✅ Вкладка закрыта.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{str(e)[:200]}</code>")

    # ------------------------------------------------------------------ #
    # /play, /pause — текстовые шорткаты (управление через кнопки пульта)      #
    # (реальная логика в player.py, здесь только text-команды без inline) #
    # ------------------------------------------------------------------ #

    @r.message(Command("play"))
    async def cmd_play(message: Message) -> None:
        if not await _guard(message):
            return
        await message.answer("▶️ Используй /mediastat для просмотра пульта,\nили /find для поиска видео.")

    @r.message(Command("pause"))
    async def cmd_pause_hint(message: Message) -> None:
        if not await _guard(message):
            return
        await message.answer("ℹ️ Используй кнопку ⏸ на пульте или голосовую команду «пауза».")

    # ------------------------------------------------------------------ #
    # /stop                                                                #
    # ------------------------------------------------------------------ #

    @r.message(Command("stop"))
    async def cmd_stop(message: Message) -> None:
        """Two-step stop with confirmation."""
        if not await _guard(message):
            return
        text = message.text or ""
        user_id = message.from_user.id  # type: ignore[union-attr]
        timeout = int(settings.get("STOP_CONFIRM_TIMEOUT_SECONDS", DEFAULT_STOP_CONFIRM_TIMEOUT_SECONDS))

        if STOP_CONFIRM_SUFFIX in text.lower():
            confirm_time = _stop_confirmations.get(user_id)
            if confirm_time and datetime.now() - confirm_time < timedelta(seconds=timeout):
                await message.answer("🛑 Бот останавливается...")
                logger.info("Bot stop confirmed by owner")
                await browser.stop()
                idle_watcher.stop()
                asyncio.get_event_loop().call_later(1, lambda: asyncio.get_event_loop().stop())
                return
            else:
                _stop_confirmations.pop(user_id, None)
                await message.answer("⏰ Таймаут истёк. Отправь /stop снова.")
                return

        _stop_confirmations[user_id] = datetime.now()
        await message.answer(
            f"⚠️ <b>Подтвердить остановку?</b>\n\n"
            f"Отправь <code>/stop confirm</code> в течение {timeout} секунд.\n\n"
            f"<i>Браузер и все фоновые задачи будут остановлены.</i>"
        )

    # ------------------------------------------------------------------ #
    # Callback: quick-action buttons from /start                          #
    # ------------------------------------------------------------------ #

    from aiogram import F

    @r.callback_query(F.data == "cmd:help")
    async def cb_help(callback) -> None:
        if not await check_access(callback.from_user.id, bot, settings):
            return
        await callback.answer()
        await callback.message.answer(
            "📖 Отправь /help для полного списка команд."
        )

    @r.callback_query(F.data == "cmd:status")
    async def cb_status(callback) -> None:
        if not await check_access(callback.from_user.id, bot, settings):
            return
        await callback.answer()
        whisper_model = settings.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL)
        await callback.message.answer(
            format_status_message(
                current_url=browser.get_current_url(),
                whisper_model=whisper_model,
                version=APP_VERSION,
            )
        )

    @r.callback_query(F.data == "cmd:shot")
    async def cb_shot(callback) -> None:
        if not await check_access(callback.from_user.id, bot, settings):
            return
        await callback.answer("📸")
        if not browser.is_running:
            await callback.message.answer("ℹ️ Браузер не запущен.")
            return
        try:
            png_bytes = await browser.take_screenshot()
            idle_watcher.reset()
            current_url = browser.get_current_url() or "—"
            await callback.message.answer_photo(
                photo=BufferedInputFile(png_bytes, filename="screenshot.png"),
                caption=sanitize_caption(f"📸 {current_url}"),
            )
        except Exception as e:
            await callback.message.answer(f"❌ {str(e)[:200]}")

    @r.callback_query(F.data == "cmd:search_hint")
    async def cb_search_hint(callback) -> None:
        if not await check_access(callback.from_user.id, bot, settings):
            return
        await callback.answer()
        await callback.message.answer(
            "🔍 Для поиска в интернете:\n<code>/search рецепт борща</code>\n\n"
            "📺 Для поиска видео:\n<code>/find Интерстеллар</code>\n"
            "или\n<code>/find рутуб Слово пацана</code>"
        )

    return r
