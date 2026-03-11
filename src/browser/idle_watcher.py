# src/browser/idle_watcher.py
"""
Browser idle timeout watcher.
Закрывает браузер автоматически после N минут бездействия
и уведомляет владельца в Telegram.
"""

import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from loguru import logger

from src.config.constants import DEFAULT_IDLE_TIMEOUT_MINUTES
from src.config.settings import Settings

# Интервал проверки бездействия — каждые 60 секунд
_CHECK_INTERVAL_SECONDS = 60


class IdleWatcher:
    """
    Background task that monitors browser activity.
    Запускается после открытия первой страницы.
    Останавливается при закрытии браузера или остановке бота.

    Принцип работы: при каждой команде браузеру вызывается reset().
    Если reset() не вызывался дольше timeout_minutes — закрываем браузер.
    """

    def __init__(self, settings: Settings, bot: Bot, owner_id: int) -> None:
        self._settings = settings
        self._bot = bot
        self._owner_id = owner_id
        self._last_activity: datetime = datetime.now()
        self._task: asyncio.Task | None = None

    def reset(self) -> None:
        """
        Reset idle timer. Call this on every browser command.
        Должен вызываться из хендлеров при каждом успешном действии с браузером.
        """
        self._last_activity = datetime.now()

    def start(self) -> None:
        """Start the background idle monitoring task."""
        if self._task and not self._task.done():
            logger.debug("IdleWatcher already running")
            return
        self._task = asyncio.create_task(self._watch_loop(), name="idle_watcher")
        logger.info("IdleWatcher started")

    def stop(self) -> None:
        """Cancel the background monitoring task."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("IdleWatcher stopped")

    async def _watch_loop(self) -> None:
        """
        Main monitoring loop. Checks for inactivity every CHECK_INTERVAL_SECONDS.
        При обнаружении таймаута вызывает _on_timeout() и останавливается.
        """
        timeout_minutes: int = int(
            self._settings.get("IDLE_TIMEOUT_MINUTES", DEFAULT_IDLE_TIMEOUT_MINUTES)
        )
        timeout_delta = timedelta(minutes=timeout_minutes)

        logger.debug(f"IdleWatcher loop running, timeout={timeout_minutes}min")

        try:
            while True:
                await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
                idle_for = datetime.now() - self._last_activity
                if idle_for >= timeout_delta:
                    logger.info(
                        f"Idle timeout reached: {idle_for.seconds // 60}min "
                        f">= {timeout_minutes}min"
                    )
                    await self._on_timeout(timeout_minutes)
                    break
        except asyncio.CancelledError:
            logger.debug("IdleWatcher cancelled")

    async def _on_timeout(self, timeout_minutes: int) -> None:
        """
        Called when idle timeout is reached.
        Уведомляем владельца — браузер закроет вызывающий код.
        """
        try:
            await self._bot.send_message(
                self._owner_id,
                f"⏱ <b>Браузер закрыт по таймауту</b>\n"
                f"Нет активности {timeout_minutes} минут.\n\n"
                f"Следующая команда откроет браузер заново.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to send idle timeout notification: {e}")
