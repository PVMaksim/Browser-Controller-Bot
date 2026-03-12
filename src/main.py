# src/main.py
"""
Entry point — Stage 7 + 8 (final).
macOS: menu bar icon + system notification в режиме onboarding.
Windows: корректно запускается как NSSM-сервис.
"""

# ── PyInstaller fix: restore missing platform attributes ──────────────────────
# PyInstaller's bootloader replaces stdlib platform with a minimal stub.
# Patch ALL missing attributes before any library import touches platform.
import sys as _sys
import platform as _platform

def _p(name, fn):
    if not hasattr(_platform, name):
        setattr(_platform, name, fn)

_p('system',                lambda: 'Darwin' if _sys.platform == 'darwin' else ('Windows' if _sys.platform == 'win32' else 'Linux'))
_p('node',                  lambda: '')
_p('release',               lambda: '')
_p('version',               lambda: '')
_p('machine',               lambda: _sys.platform)
_p('processor',             lambda: '')
_p('architecture',          lambda bits='', linkage='': (bits, linkage))
_p('python_implementation', lambda: 'CPython')
_p('python_version',        lambda: '.'.join(str(x) for x in _sys.version_info[:3]))
_p('python_version_tuple',  lambda: tuple(str(x) for x in _sys.version_info[:3]))
_p('python_build',          lambda: ('', ''))
_p('python_compiler',       lambda: '')
_p('python_branch',         lambda: '')
_p('python_revision',       lambda: '')
_p('mac_ver',               lambda terse=False, release='', versioninfo=('','',''), machine='': (release, versioninfo, machine))
_p('win32_ver',             lambda release='', version='', csd='', ptype='': (release, version, csd, ptype))
_p('win32_edition',         lambda: '')
_p('win32_is_iot',          lambda: False)
_p('uname',                 lambda: _platform.uname_result('','','','','','') if hasattr(_platform,'uname_result') else ('','','','','',''))
_p('platform',              lambda aliased=False, terse=False: '')
del _p
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from src.browser.engine import BrowserEngine
from src.browser.idle_watcher import IdleWatcher
from src.browser.watchdog import BrowserWatchdog
from src.ocr.core import OCRProcessor
from src.config.constants import APP_VERSION
from src.config.logging import setup_logging
from src.config.settings import Settings
from src.handlers.commands import get_command_router
from src.handlers.onboarding import get_onboarding_router
from src.handlers.player import get_player_router
from src.handlers.system_commands import get_system_router
from src.handlers.photo import get_photo_router
from src.handlers.voice import get_voice_router
from src.middlewares.error_handler import notify_owner_on_error
from src.middlewares.rate_limiter import RateLimiterMiddleware
from src.player.controller import PlayerController
from src.voice.processor import VoiceProcessor


async def main() -> None:
    """Initialize and start the bot (all stages)."""
    settings = Settings()
    setup_logging(level=settings.get("LOG_LEVEL", "INFO"))

    logger.info(f"Secure Browser Bot v{APP_VERSION} starting...")

    try:
        bot_token = settings.require("BOT_TOKEN")
    except ValueError as e:
        logger.critical(str(e))
        sys.exit(1)

    is_onboarding = settings.is_onboarding_mode()

    if is_onboarding:
        logger.warning(
            "\n"
            "═══════════════════════════════════════════\n"
            "  ⚠️  РЕЖИМ ПЕРВОГО ЗАПУСКА (ONBOARDING)\n"
            "  Отправьте /register своему боту в Telegram\n"
            "  чтобы зарегистрироваться как владелец.\n"
            "═══════════════════════════════════════════"
        )
        # macOS system notification для первого запуска
        _show_onboarding_notification()

    owner_id_raw = settings.get("ALLOWED_USER_ID")
    owner_id = int(owner_id_raw) if owner_id_raw else 0

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    browser = BrowserEngine(settings=settings)
    idle_watcher = IdleWatcher(settings=settings, bot=bot, owner_id=owner_id)
    voice_processor = VoiceProcessor(settings=settings)
    player = PlayerController(
        settings=settings, browser=browser, bot=bot, owner_id=owner_id
    )

    dp = Dispatcher()

    ocr_processor = OCRProcessor(settings=settings)

    # Rate limiter — отбрасываем флуд до обработки роутерами
    dp.message.middleware(RateLimiterMiddleware())

    # Порядок роутеров критичен — onboarding первый
    dp.include_router(get_onboarding_router(settings=settings, bot=bot))
    dp.include_router(get_command_router(settings=settings, bot=bot,
                                         browser=browser, idle_watcher=idle_watcher,
                                         watchdog=watchdog, ocr_processor=ocr_processor))
    dp.include_router(get_player_router(settings=settings, bot=bot, player=player))
    dp.include_router(get_system_router(settings=settings, bot=bot))
    dp.include_router(get_voice_router(settings=settings, bot=bot, browser=browser,
                                        idle_watcher=idle_watcher,
                                        voice_processor=voice_processor, player=player))

    @dp.errors()
    async def global_error_handler(event, exception: Exception) -> bool:
        logger.exception(f"Unhandled error: {exception}")
        try:
            await notify_owner_on_error(
                bot=bot, settings=settings,
                error=exception, context=str(event),
            )
        except Exception:
            pass
        return True

    # Menu bar icon (macOS only, no-op on Windows/Linux)
    _start_menu_bar(bot=bot, browser=browser, idle_watcher=idle_watcher, player=player)

    # Watchdog — запускаем после browser.start()
    owner_id_raw = settings.get("ALLOWED_USER_ID", "0")
    owner_id = int(owner_id_raw) if owner_id_raw and owner_id_raw.isdigit() else 0
    watchdog = BrowserWatchdog(browser=browser, settings=settings, bot=bot, owner_id=owner_id)
    if not is_onboarding:
        watchdog.start()

    logger.info("Bot ready. Starting polling...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down...")
        idle_watcher.stop()
        watchdog.stop()
        player._cancel_background_tasks()
        await browser.stop()
        await bot.session.close()
        logger.info("Shutdown complete.")


# ------------------------------------------------------------------ #
# Helpers (platform-specific, no-op if deps missing)                  #
# ------------------------------------------------------------------ #

def _show_onboarding_notification() -> None:
    """Show macOS system notification with onboarding instruction."""
    try:
        from src.platform.menu_bar import show_notification
        show_notification(
            title="Secure Browser Bot",
            message="Отправьте /register своему боту в Telegram",
            subtitle="Первый запуск — регистрация владельца",
        )
    except Exception:
        pass  # Некритично — пользователь увидит инструкцию в Telegram


def _start_menu_bar(
    bot: Bot,
    browser: BrowserEngine,
    idle_watcher: IdleWatcher,
    player: PlayerController,
) -> None:
    """Start menu bar icon (macOS). Safe no-op if rumps not installed."""
    try:
        from src.platform.menu_bar import start_menu_bar
        from src.utils.system_info import format_status_message

        def on_quit() -> None:
            idle_watcher.stop()
            player._cancel_background_tasks()
            asyncio.get_event_loop().stop()

        def on_status() -> str:
            current_url = browser.get_current_url()
            return (
                f"Бот активен\n"
                f"Браузер: {current_url or 'не запущен'}\n"
                f"Плеер: {'активен' if player.state.is_active else 'не активен'}"
            )

        start_menu_bar(on_quit=on_quit, on_status=on_status)
    except Exception:
        pass  # Menu bar опционален


if __name__ == "__main__":
    asyncio.run(main())
