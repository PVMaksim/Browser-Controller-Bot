# src/main.py
"""
Entry point — Stage 7 + 8 (final).
macOS: menu bar icon + system notification в режиме onboarding.
Windows: корректно запускается как NSSM-сервис.
"""

# ── PyInstaller fix: patch Dispatcher.include_router at import time ───────────
import sys as _sys
import aiogram.dispatcher.router as _adr
import aiogram.dispatcher.dispatcher as _add

def _force_include_router(self, router):
    """
    Drop-in for Router.include_router that accepts routers from any import path.
    Fixes PyInstaller double-import where isinstance(router, Router) == False
    even though router IS a Router, just from a different sys.modules entry.
    """
    Router = type(self)
    # Accept if real Router or duck-typed Router (same attrs, different class obj)
    if not isinstance(router, _adr.Router):
        if not (hasattr(router, 'observers') and hasattr(router, '_parent')):
            raise ValueError("router should be instance of Router not type")
        # Remap the frozen module so both sides see the same class
        mod_name = type(router).__module__
        if mod_name in _sys.modules:
            _sys.modules[mod_name].Router = _adr.Router
        # Re-instantiate as the canonical Router
        canonical = _adr.Router.__new__(_adr.Router)
        canonical.__dict__.update(router.__dict__)
        router = canonical

    # Inline the real include_router logic (avoids calling self which would recurse)
    if router._parent is not None:
        raise RuntimeError(
            f"Router [{router!r}] is already attached to another router [{router._parent!r}]."
        )
    router._parent = self
    self._routers.append(router)
    # Propagate parent's filters to child
    for name, observer in router.observers.items():
        if name in self.observers:
            for f in self.observers[name].filters:
                observer.filter(f)
    return router

_adr.Router.include_router = _force_include_router
if hasattr(_add, 'Dispatcher'):
    _add.Dispatcher.include_router = _force_include_router
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
    dp.include_router(get_photo_router(settings=settings, bot=bot,
                                       ocr_processor=ocr_processor))

    # Global error handler (aiogram 3 compatible)
    errors_router = Router()

    @errors_router.errors()
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

    dp.include_router(errors_router)

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
