# src/browser/stealth.py
"""
Browser-type-aware stealth layer.

Проблема «одного stealth для всех»:
  - Firefox с window.chrome = {} выглядит подозрительнее, чем без патча
  - WebKit не знает Chromium JS API — патчи создают аномалии
  - Chrome UA в Firefox — мгновенный red flag для антибот-систем

Решение:
  1. StealthConfig с разными наборами патчей для каждого браузера
  2. UA-пул разбит по типам — каждый браузер получает правдоподобный UA
  3. Дополнительные JS-патчи, специфичные для Firefox / WebKit

playwright_stealth StealthConfig флаги и применимость:
  navigator_webdriver           — все браузеры  ✓
  navigator_plugins             — только Chromium
  navigator_languages           — все браузеры  ✓
  user_agent_override           — отключаем (UA управляем через пул)
  webgl_vendor                  — только Chromium
  chrome_app / chrome_runtime   — только Chromium
  iframe_content_window         — только Chromium
  media_codecs                  — только Chromium
  hairline_fix                  — все браузеры  ✓
  navigator_hardware_concurrency — все браузеры  ✓
"""

import random
from loguru import logger
from playwright.async_api import Page


# ------------------------------------------------------------------ #
# 1. Browser-typed UA pools                                            #
# ------------------------------------------------------------------ #

_UA_POOLS: dict[str, list[str]] = {
    "chromium": [
        # Chrome 120–124, macOS Intel
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        # Chrome 120–124, macOS M-chip
        "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_2_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        # Chrome 120–124, Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ],
    "firefox": [
        # Firefox 121–125, macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
        # Firefox 121–125, Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ],
    "webkit": [
        # Safari 17.x, macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
        # Safari, macOS M-chip
        "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ],
}
# «chrome» — alias для chromium
_UA_POOLS["chrome"] = _UA_POOLS["chromium"]


def get_user_agent(browser_type: str) -> str:
    """
    Return a random UA string matching the given browser type.
    Каждый браузер получает правдоподобный для него UA:
    Firefox → Firefox UA, WebKit → Safari UA, Chromium → Chrome UA.
    Фиксируется на сессию в engine.py — не меняется между запросами.
    """
    pool = _UA_POOLS.get(browser_type.lower(), _UA_POOLS["chromium"])
    return random.choice(pool)


def get_ua_pool(browser_type: str) -> list[str]:
    """Return a copy of the UA pool for a browser type (для тестов)."""
    return list(_UA_POOLS.get(browser_type.lower(), _UA_POOLS["chromium"]))


# ------------------------------------------------------------------ #
# 2. StealthConfig per browser type                                    #
# ------------------------------------------------------------------ #

def _make_config(browser_type: str):
    """
    Build StealthConfig appropriate for the given browser type.
    Возвращает None если playwright_stealth недоступен или версия не поддерживает аргументы.
    """
    try:
        from playwright_stealth import StealthConfig
    except ImportError:
        return None

    bt = browser_type.lower()

    # Пробуем полную конфигурацию, при ошибке — минимальную
    try:
        if bt in ("chromium", "chrome"):
            return StealthConfig(
                navigator_webdriver=True,
                navigator_plugins=True,
                navigator_languages=True,
                user_agent_override=False,
                webgl_vendor=True,
                chrome_app=True,
                chrome_runtime=True,
                iframe_content_window=True,
                media_codecs=True,
                hairline_fix=True,
                navigator_hardware_concurrency=True,
            )
        elif bt == "firefox":
            return StealthConfig(
                navigator_webdriver=True,
                navigator_plugins=False,
                navigator_languages=True,
                user_agent_override=False,
                webgl_vendor=False,
                chrome_app=False,
                chrome_runtime=False,
                iframe_content_window=False,
                media_codecs=False,
                hairline_fix=True,
                navigator_hardware_concurrency=True,
            )
        else:
            return StealthConfig(
                navigator_webdriver=True,
                navigator_plugins=False,
                navigator_languages=True,
                user_agent_override=False,
                webgl_vendor=False,
                chrome_app=False,
                chrome_runtime=False,
                iframe_content_window=False,
                media_codecs=False,
                hairline_fix=True,
                navigator_hardware_concurrency=True,
            )
    except TypeError:
        # Версия playwright-stealth не поддерживает часть аргументов — используем дефолты
        logger.warning("playwright-stealth: unsupported StealthConfig args, using defaults")
        try:
            return StealthConfig()
        except Exception:
            return None


# ------------------------------------------------------------------ #
# 3. Extra JS patches per browser type                                 #
# ------------------------------------------------------------------ #

# Chromium-патчи живут в antibot.py (_EXTRA_JS_PATCHES).
# Здесь — Firefox и WebKit.

_FIREFOX_PATCHES = """
try { Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); } catch(e) {}
try {
    Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
    Object.defineProperty(navigator, 'language',  {get: () => 'ru-RU'});
} catch(e) {}
try { delete window.__pwInitScripts; } catch(e) {}
try { delete window.__playwright; } catch(e) {}
"""

_WEBKIT_PATCHES = """
try { Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); } catch(e) {}
try {
    Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
    Object.defineProperty(navigator, 'language',  {get: () => 'ru-RU'});
} catch(e) {}
try { delete window.__pwInitScripts; } catch(e) {}
"""

_EXTRA_PATCHES: dict[str, str] = {
    "firefox": _FIREFOX_PATCHES,
    "webkit":  _WEBKIT_PATCHES,
}


def get_extra_patches(browser_type: str) -> str | None:
    """
    Return browser-specific JS init-script, or None for Chromium
    (Chromium patches are in antibot.py and applied via inject_extra_patches).
    """
    return _EXTRA_PATCHES.get(browser_type.lower())


# ------------------------------------------------------------------ #
# 4. Public API                                                        #
# ------------------------------------------------------------------ #

def is_available() -> bool:
    """Return True if playwright-stealth is installed."""
    try:
        import importlib.util
        return importlib.util.find_spec("playwright_stealth") is not None
    except Exception:
        return False


async def apply(page: Page, browser_type: str) -> bool:
    """
    Apply browser-appropriate stealth to a page.
    Returns True if stealth was applied, False if unavailable or failed.
    Всегда graceful — не бросает исключений.
    """
    config = _make_config(browser_type)
    if config is None:
        return False
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page, config)
        logger.debug(f"Stealth applied [{browser_type}]")
        return True
    except Exception as e:
        logger.warning(f"Stealth failed [{browser_type}]: {e}")
        return False
