# src/player/ad_handler.py
"""
Three-level ad protection:
  Level 1 — uBlock Origin extension in browser profile (blocks ~90% before load)
  Level 2 — Playwright watches for skip buttons and clicks them automatically
  Level 3 — JS detector notifies in Telegram if ad still plays

Все три уровня работают параллельно и независимо.
Пользователь не замечает рекламу.
"""

import asyncio

from aiogram import Bot
from loguru import logger
from playwright.async_api import Page

# Селекторы кнопок «Пропустить рекламу» для каждой платформы
_SKIP_SELECTORS: dict[str, str] = {
    "youtube": ".ytp-skip-ad-button, .videoAdUiSkipButton, .ytp-ad-skip-button",
    "rutube":  "[class*='skip' i], [class*='Skip'], [data-label*='пропустить' i]",
    "vk":      ".ad_skip_btn, [class*='skip' i]",
    "ok":      ".skip-ad, [class*='skip' i]",
}

# CSS-селекторы присутствия рекламного оверлея
_AD_PRESENCE_SELECTORS: list[str] = [
    ".ad-container",
    ".advertisement",
    "[class*='ad-playing' i]",
    "[class*='AdPlaying']",
    ".ytp-ad-player-overlay",
    "[class*='AdvBlock']",
]


async def watch_and_skip_ads(page: Page, platform: str) -> None:
    """
    Background task: detect skip button and click it as soon as it appears.
    Запускается параллельно с воспроизведением через asyncio.create_task().
    Не блокирует команды управления плеером.
    Завершается когда page закрыта или задача отменена.
    """
    selector = _SKIP_SELECTORS.get(platform, "[class*='skip' i]")
    logger.debug(f"Ad watcher started for platform={platform}")

    while True:
        try:
            skip_btn = page.locator(selector).first
            if await skip_btn.is_visible(timeout=500):
                await skip_btn.click()
                logger.info(f"Ad skipped on {platform}")
        except asyncio.CancelledError:
            logger.debug(f"Ad watcher cancelled for {platform}")
            return
        except Exception:
            pass  # Кнопки нет — всё нормально, продолжаем мониторинг
        await asyncio.sleep(1)


async def is_ad_playing(page: Page) -> bool:
    """
    Detect if an advertisement is currently playing via JS DOM check.
    Используется для Level 3 — уведомления если реклама всё же проскочила.
    """
    try:
        selectors_js = ", ".join(f'"{s}"' for s in _AD_PRESENCE_SELECTORS)
        return await page.evaluate(f"""() => {{
            const selectors = [{selectors_js}];
            return selectors.some(s => document.querySelector(s) !== null);
        }}""")
    except Exception:
        return False


async def notify_if_ad_playing(page: Page, bot: Bot, owner_id: int) -> None:
    """
    Level 3: check for ad and notify owner in Telegram if detected.
    Вызывается один раз после открытия видео — информационное уведомление.
    """
    if await is_ad_playing(page):
        try:
            await bot.send_message(
                owner_id,
                "📢 <b>Идёт реклама</b>\n"
                "uBlock не заблокировал. Жду кнопку «Пропустить»...",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to send ad notification: {e}")
