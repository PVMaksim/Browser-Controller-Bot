# src/browser/antibot.py
"""
Antibot utilities: human behavior simulation, cookie banner dismissal,
and additional JS patches to hide browser automation.

Используется платформами медиапульта для снижения вероятности
блокировки антибот-системами RuTube, YouTube, VK, ОК.

Три вида защиты:
  1. Случайные задержки между действиями — имитация чтения/реакции
  2. Обход cookie/GDPR-баннеров — иначе они перекрывают контент
  3. Дополнительные JS-патчи — скрываем специфические следы автоматизации
"""

import asyncio
import random

from loguru import logger
from playwright.async_api import Page


# ------------------------------------------------------------------ #
# 1. Human-like delays                                                 #
# ------------------------------------------------------------------ #

async def human_delay(min_ms: int = 300, max_ms: int = 1200) -> None:
    """
    Sleep a random amount to simulate human reaction time.
    Минимальная задержка 300мс — ниже этого браузер выглядит как бот.
    """
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)


async def human_scroll(page: Page, scrolls: int = 2) -> None:
    """
    Simulate human scrolling down the page.
    Случайная скорость и дистанция — паттерн реального пользователя.
    """
    for _ in range(scrolls):
        distance = random.randint(200, 600)
        await page.evaluate(f"window.scrollBy(0, {distance})")
        await asyncio.sleep(random.uniform(0.2, 0.6))


async def human_move_mouse(page: Page) -> None:
    """
    Move mouse to a random position on the page.
    Некоторые антибот-системы отслеживают отсутствие движений мыши.
    """
    try:
        width = await page.evaluate("window.innerWidth")
        height = await page.evaluate("window.innerHeight")
        x = random.randint(100, max(200, width - 100))
        y = random.randint(100, max(200, height - 100))
        await page.mouse.move(x, y)
    except Exception:
        pass  # Некритично — мышь опциональна


# ------------------------------------------------------------------ #
# 2. Cookie / consent banner dismissal                                 #
# ------------------------------------------------------------------ #

# Селекторы кнопок согласия для каждой платформы
# Обновляются вместе с изменением вёрстки платформ
_COOKIE_SELECTORS: dict[str, list[str]] = {
    "rutube": [
        "button[data-testid='cookie-policy-accept']",
        "[class*='CookiePolicy'] button",
        "[class*='cookie'] button",
        "button:has-text('Принять')",
        "button:has-text('Согласен')",
    ],
    "youtube": [
        "button[aria-label='Accept all']",
        "button[aria-label='Принять все']",
        ".eom-button-row button:last-child",
        "ytd-consent-bump-v2-lightbox button:last-child",
        "tp-yt-paper-button[aria-label*='ccept']",
    ],
    "vk": [
        ".VkIdForm__submitButton",
        "[class*='cookie'] button",
        "button:has-text('Принять')",
        "#cookie-policy-accept",
    ],
    "ok": [
        "#cookie-consent-btn",
        ".cookie-notice__accept",
        "button:has-text('Принять')",
        "button:has-text('OK')",
    ],
}

# Общие селекторы — проверяются для всех платформ
_GENERIC_COOKIE_SELECTORS = [
    "[id*='cookie'] button",
    "[class*='cookie-accept']",
    "[class*='consent'] button[class*='accept']",
    "button:has-text('Принять все')",
    "button:has-text('Принять')",
    "button:has-text('Согласиться')",
]


async def dismiss_cookie_banner(page: Page, platform: str = "") -> bool:
    """
    Find and click cookie consent / GDPR banner accept button.
    Returns True if banner was found and dismissed.

    Платформо-специфичные селекторы проверяются первыми,
    затем общие. Если ничего не найдено — тихо возвращает False.
    """
    selectors = _COOKIE_SELECTORS.get(platform, []) + _GENERIC_COOKIE_SELECTORS

    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=500):
                await btn.click()
                await human_delay(200, 500)
                logger.debug(f"Cookie banner dismissed on {platform or 'unknown'}")
                return True
        except Exception:
            continue

    return False


# ------------------------------------------------------------------ #
# 3. Additional JS patches (injected before page load)                 #
# ------------------------------------------------------------------ #

# JavaScript патчи — скрывают дополнительные следы Playwright/CDP
# которые playwright-stealth не покрывает
_EXTRA_JS_PATCHES = """
// Скрываем navigator.webdriver (playwright-stealth уже делает это, дублируем для надёжности)
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Фиксируем chrome.runtime — некоторые сайты проверяют его наличие
if (!window.chrome) {
    window.chrome = { runtime: {} };
}

// Реалистичные размеры экрана
Object.defineProperty(screen, 'width',       {get: () => 1920});
Object.defineProperty(screen, 'height',      {get: () => 1080});
Object.defineProperty(screen, 'availWidth',  {get: () => 1920});
Object.defineProperty(screen, 'availHeight', {get: () => 1040});
Object.defineProperty(screen, 'colorDepth',  {get: () => 24});
Object.defineProperty(screen, 'pixelDepth',  {get: () => 24});

// Реалистичные navigator.plugins (Chrome имеет встроенные плагины)
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
        {name: 'Chrome PDF Viewer',  filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
        {name: 'Native Client',      filename: 'internal-nacl-plugin'},
    ]
});

// Реалистичные navigator.languages
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
Object.defineProperty(navigator, 'language',  {get: () => 'ru-RU'});

// Скрываем специфический для Playwright __pwInitScripts
try { delete window.__pwInitScripts; } catch(e) {}
"""


async def inject_extra_patches(page: Page) -> None:
    """
    Inject additional JS patches that playwright-stealth might miss.
    Вызывается один раз при создании страницы, до любой навигации.

    Использует addInitScript — патч применяется ко ВСЕМ последующим
    загрузкам страниц в этом контексте, включая SPA-навигацию.
    """
    try:
        await page.add_init_script(_EXTRA_JS_PATCHES)
        logger.debug("Extra JS antibot patches injected")
    except Exception as e:
        logger.debug(f"Extra patches injection failed (non-critical): {e}")


# ------------------------------------------------------------------ #
# 4. Chromium launch args for engine.py                               #
# ------------------------------------------------------------------ #

# Полный набор Chromium-флагов для скрытия автоматизации.
# Импортируется в engine.py при создании контекста.
CHROMIUM_ANTIBOT_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",          # Предотвращает сбои на системах с малым /dev/shm
    "--no-sandbox",                     # Нужен в некоторых средах; не влияет на безопасность в изолированном профиле
    "--disable-infobars",               # Убирает баннер «Chrome is being controlled by automated software»
    "--disable-extensions-except=",    # Отключаем лишние расширения, кроме явно указанных
    "--disable-default-apps",
    "--disable-component-update",
    "--disable-background-networking",
    "--disable-sync",
    "--metrics-recording-only",
    "--disable-client-side-phishing-detection",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--use-mock-keychain",              # macOS: не обращаемся к связке ключей
    "--disable-features=TranslateUI,BlinkGenPropertyTrees,ImprovedCookieControls,"
    "LazyFrameLoading,GlobalMediaControls",
    "--enable-features=NetworkService,NetworkServiceLogging",
]

# ------------------------------------------------------------------ #
# 5. User-Agent — re-exported from stealth.py                         #
# ------------------------------------------------------------------ #
# UA пулы перенесены в src/browser/stealth.py (browser-typed pools).
# Эти обёртки сохраняют обратную совместимость с тестами и внешним кодом.

def get_random_user_agent(browser_type: str = "chromium") -> str:
    """Return a random UA matching browser_type. Delegates to stealth.get_user_agent()."""
    from src.browser.stealth import get_user_agent
    return get_user_agent(browser_type)


def get_user_agent_pool(browser_type: str = "chromium") -> list[str]:
    """Return UA pool for browser_type. Delegates to stealth.get_ua_pool()."""
    from src.browser.stealth import get_ua_pool
    return get_ua_pool(browser_type)
