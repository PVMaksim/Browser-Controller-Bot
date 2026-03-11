# src/browser/watchdog.py
"""
Browser watchdog — hang detection and auto-restart.

Зачем нужен:
  Playwright на macOS/Windows может зависнуть после:
    - Долгого idle (системный сон без закрытия браузера)
    - OOM-убийства рендер-процесса
    - Зависших JS-промисов на видео-платформах
    - Редких гонок в Playwright

  Без watchdog бот становится «мёртвым»: принимает команды, но не реагирует.

Стратегия:
  1. Каждые CHECK_INTERVAL_SEC пробуем выполнить лёгкую JS-операцию
  2. Если evaluate() таймаутит или бросает — браузер завис
  3. Останавливаем старый контекст, запускаем новый
  4. Уведомляем владельца через Telegram

Не трогаем плеер и историю просмотра — watchdog работает независимо.
"""

import asyncio

from aiogram import Bot
from loguru import logger

from src.browser.engine import BrowserEngine
from src.config.constants import (
    WATCHDOG_CHECK_INTERVAL_SEC,
    WATCHDOG_PROBE_TIMEOUT_MS,
    WATCHDOG_MAX_RESTARTS,
)
from src.config.settings import Settings


class BrowserWatchdog:
    """
    Periodically probes the browser and restarts it if it hangs.
    Один экземпляр на весь жизненный цикл бота.
    """

    def __init__(
        self,
        browser: BrowserEngine,
        settings: Settings,
        bot: Bot,
        owner_id: int,
    ) -> None:
        self._browser = browser
        self._settings = settings
        self._bot = bot
        self._owner_id = owner_id

        self._task: asyncio.Task | None = None
        self._restart_count: int = 0
        self._running: bool = False

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the watchdog loop as a background asyncio task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="browser_watchdog")
        logger.info(
            f"Browser watchdog started "
            f"(interval={WATCHDOG_CHECK_INTERVAL_SEC}s, "
            f"probe_timeout={WATCHDOG_PROBE_TIMEOUT_MS}ms)"
        )

    def stop(self) -> None:
        """Stop the watchdog loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Browser watchdog stopped")

    # ------------------------------------------------------------------ #
    # Core loop                                                            #
    # ------------------------------------------------------------------ #

    async def _loop(self) -> None:
        """Main watchdog loop: probe → restart if needed → sleep."""
        while self._running:
            try:
                await asyncio.sleep(WATCHDOG_CHECK_INTERVAL_SEC)
                if not self._running:
                    break

                # Не трогаем если браузер не запущен — это нормальное состояние
                if not self._browser.is_running:
                    logger.debug("Watchdog: browser not running, skipping probe")
                    continue

                alive = await self._probe()
                if not alive:
                    await self._handle_hang()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog loop error (non-fatal): {e}")

    async def _probe(self) -> bool:
        """
        Probe the browser with a lightweight JS evaluation.
        Returns True if browser responds within timeout, False otherwise.
        Таймаут намеренно короткий — зависший браузер не должен держать нас долго.
        """
        page = self._browser.get_page()
        if page is None:
            return False

        try:
            result = await asyncio.wait_for(
                page.evaluate("() => typeof window !== 'undefined'"),
                timeout=WATCHDOG_PROBE_TIMEOUT_MS / 1000,
            )
            return bool(result)
        except asyncio.TimeoutError:
            logger.warning(
                f"Watchdog probe timed out after {WATCHDOG_PROBE_TIMEOUT_MS}ms — browser may be hung"
            )
            return False
        except Exception as e:
            logger.warning(f"Watchdog probe failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Restart                                                              #
    # ------------------------------------------------------------------ #

    async def _handle_hang(self) -> None:
        """Restart hung browser and notify owner."""
        self._restart_count += 1

        if self._restart_count > WATCHDOG_MAX_RESTARTS:
            logger.error(
                f"Watchdog: max restarts ({WATCHDOG_MAX_RESTARTS}) reached. "
                "Stopping watchdog to prevent restart loop."
            )
            await self._notify_owner(
                "🚨 <b>Браузер завис (максимум перезапусков достигнут)</b>\n\n"
                f"Перезапусков: {self._restart_count - 1}\n"
                "Watchdog остановлен. Перезапусти бота вручную: <code>/stop confirm</code>",
                critical=True,
            )
            self.stop()
            return

        logger.warning(
            f"Watchdog: browser hung, restarting "
            f"(attempt {self._restart_count}/{WATCHDOG_MAX_RESTARTS})"
        )

        try:
            await self._browser.stop()
        except Exception as e:
            logger.error(f"Watchdog: error stopping browser: {e}")

        try:
            await self._browser.start()
            logger.info("Watchdog: browser restarted successfully")
            await self._notify_owner(
                f"🔄 <b>Браузер перезапущен</b>\n\n"
                f"Watchdog обнаружил зависание и перезапустил браузер.\n"
                f"Перезапуск #{self._restart_count}."
            )
        except Exception as e:
            logger.error(f"Watchdog: failed to restart browser: {e}")
            await self._notify_owner(
                f"❌ <b>Не удалось перезапустить браузер</b>\n\n"
                f"<code>{str(e)[:300]}</code>",
                critical=True,
            )

    async def _notify_owner(self, text: str, critical: bool = False) -> None:
        """Send watchdog notification to bot owner. Silent on failure."""
        try:
            await self._bot.send_message(
                self._owner_id,
                text,
                parse_mode="HTML",
            )
        except Exception as e:
            level = logger.error if critical else logger.warning
            level(f"Watchdog: failed to notify owner: {e}")

    # ------------------------------------------------------------------ #
    # Stats                                                                #
    # ------------------------------------------------------------------ #

    @property
    def restart_count(self) -> int:
        """Total number of browser restarts performed."""
        return self._restart_count

    @property
    def is_running(self) -> bool:
        return self._running
