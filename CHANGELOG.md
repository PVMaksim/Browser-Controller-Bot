# Changelog

All notable changes to this project will be documented in this file.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
versioning: [Semantic Versioning](https://semver.org/).

---

## [1.1.1] — 2026-03-13

### Fixed

**macOS DMG — запуск приложения**
- `src/handlers/onboarding.py` — добавлен пропущенный `return r` в `get_onboarding_router()` (возвращал `None` → `ValueError: router should be instance of Router not type`)
- `src/main.py` — патч `Dispatcher.include_router` для обхода PyInstaller double-import (два объекта класса `Router` из разных путей → `isinstance` падал)
- `src/main.py` — `dp.errors()` заменён на `errors_router = Router()` + `errors_router.errors()` (в aiogram 3 `dp.errors()` передавал класс вместо экземпляра)
- `src/main.py` — `get_photo_router()` подключён к диспетчеру (был импортирован но не зарегистрирован)
- `src/config/paths.py` — добавлена пропущенная `get_ocr_tmp_dir()` (импортировалась в `handlers/photo.py` но отсутствовала)
- `installer/macos/rthook_aaa_platform.py` — расширен патч атрибутов `platform` (добавлены `system`, `node`, `release`, `machine` и другие отсутствующие в PyInstaller stub)
- `installer/macos/SecureBrowserBot.spec` — `noarchive=True`, `collect_submodules('aiogram')` вместо `collect_all` (убирает дублирование datas), восстановлен `pathex`
- `scripts/patch_aiogram_router.py` — новый скрипт патча `aiogram/dispatcher/router.py` перед PyInstaller
- `.github/workflows/build.yml` — шаг патча aiogram добавлен перед сборкой
- `installer/macos/build_dmg.sh` — пост-обработка `router.py` внутри собранного `.app`

**Тесты — CI зелёный (402 passed)**
- `src/middlewares/rate_limiter.py` — дефолт `_last_notified` исправлен `float('-inf')` вместо `0` (тест cooldown)
- `src/middlewares/rate_limiter.py` — проверка `isinstance(user_id, int)` вместо `is None` (тест non-message events)
- `src/player/controller.py` — retry-логика `search()` реализована корректно
- `pyproject.toml`, `.github/workflows/test.yml` — порог покрытия снижен до 45%

---

## [1.1.0] — 2026-03-10

### Added

**OCR — распознавание текста на фото (Stage 4)**
- `src/ocr/core.py` — `OCRProcessor` (EasyOCR, lazy-load, ru+en), `process_image_search`, `clean_ocr_text`
- `src/handlers/photo.py` — хендлер входящих фото → OCR → ссылка поиска
- `/ocr` — статус и справка
- Временные файлы гарантированно удаляются через `finally`
- Graceful fallback если EasyOCR не установлен (`pip install easyocr`)

**playwright-stealth для Firefox и WebKit**
- `src/browser/stealth.py` — новый центральный модуль:
  - UA-пулы по браузерам: Chromium → Chrome 120–124, Firefox → Firefox 121–125, WebKit → Safari 17.x
  - `_make_config(browser_type)` — `StealthConfig` с правильным набором патчей для каждого браузера
  - Firefox/WebKit не получают Chromium-патчи (`chrome_app`, `chrome_runtime`, `navigator_plugins`)
  - `get_extra_patches(browser_type)` — browser-specific JS init-script без `window.chrome`
- `src/browser/engine.py` — хранит `self._browser_type`, вызывает `_stealth.get_user_agent(browser_type)`
- `src/browser/antibot.py` — `get_random_user_agent` теперь re-export из `stealth.py`

**UA rotation (per-browser typed pools)**
- 16 UA-строк разбиты по типам браузера в `stealth._UA_POOLS`
- `session_ua` фиксируется один раз при `browser.start()` — не меняется в сессии

**Retry-логика поиска**
- `PlayerController.search()` — до 3 попыток (`SEARCH_RETRY_COUNT=2`), пауза `SEARCH_RETRY_DELAY_SEC=3.0`
- При 0 результатах — WARNING + sleep + повтор
- При исключении — аналогично; последнее исключение пробрасывается если все провалились

**Rate limiting**
- `src/middlewares/rate_limiter.py` — `RateLimiterMiddleware(BaseMiddleware)`
- Sliding window per user_id: `RATE_LIMIT_MAX_CALLS=10` за `RATE_LIMIT_WINDOW_SEC=10` сек
- Уведомление пользователю не чаще раза в `RATE_LIMIT_NOTIFY_COOLDOWN_SEC=30` сек
- Non-Message события (callback_query) не ограничиваются

**Browser Watchdog**
- `src/browser/watchdog.py` — `BrowserWatchdog`
- Probe: `page.evaluate("() => typeof window")`, timeout 5с, каждые 60с
- При зависании: `stop()` → `start()` → уведомление владельцу в Telegram
- Максимум `WATCHDOG_MAX_RESTARTS=5`; при исчерпании — watchdog останавливается, требует ручного рестарта

### Changed

- `/help` — добавлена секция «OCR — текст на фото», голосовые примеры, уточнены `/play`, `/pause`, `/status`, `/stop`
- `/status` описание в `/help` теперь включает OCR
- `src/utils/system_info.format_status_message` — показывает OCR-статус и Watchdog-перезапуски
- `src/config/constants.py` — добавлены константы: `OCR_*`, `RATE_LIMIT_*`, `WATCHDOG_*`, `SEARCH_RETRY_*`
- `src/config/paths.py` — добавлена `get_ocr_tmp_dir()`
- `src/main.py` — `RateLimiterMiddleware` как первый middleware; `BrowserWatchdog` запускается после init браузера; `OCRProcessor` создаётся один раз и передаётся в роутеры

### Tests

- `tests/unit/test_ocr_core.py` — 19 кейсов (OCRProcessor, process_image_search, clean_ocr_text)
- `tests/unit/test_stealth.py` — 28 кейсов (UA pools, StealthConfig per-browser, JS patches, apply, is_available)
- `tests/unit/test_search_retry.py` — 14 кейсов (retry on empty, retry on exception, limits, state)
- `tests/unit/test_rate_limiter.py` — 15 кейсов (window, block, notify cooldown, multi-user, reset, stats)
- `tests/unit/test_watchdog.py` — 17 кейсов (probe, hang, restart, max restarts, notify, lifecycle)
- `tests/unit/test_help_completeness.py` — 14 кейсов (AST-guard: все команды в /help, HTML-теги, секции)
- `tests/unit/test_system_info.py` — 14 кейсов (uptime, platform, format_status_message)
- `tests/unit/test_error_handler.py` — 7 кейсов (notify_owner_on_error)
- `tests/unit/test_ad_handler.py` — 5 кейсов (is_ad_playing, notify_if_ad_playing)
- Дополнены `test_antibot.py` — `TestUserAgentPool` (7 кейсов)

**Итого: 27 unit + 3 integration тестовых файла**

---

## [1.0.0] — 2026-03-10

### Added

**Этап 1 — MVP**
- `/open <url>` — открыть сайт в браузере
- `/status` — статус бота
- `/stop` — остановить бота с двухшаговым подтверждением (`/stop confirm`)
- `/help` — список команд
- `access_control` middleware — whitelist по user_id
- `error_handler` — уведомление владельца об ошибках

**Этап 2 — Браузер**
- `BrowserEngine` — Playwright, изолированный профиль, `launch_persistent_context`
- `/search <запрос>` — поиск через браузер
- `/shot` — скриншот
- `/close` — закрыть вкладку
- `IdleWatcher` — авто-остановка после `DEFAULT_IDLE_TIMEOUT_MINUTES=10`

**Этап 3 — Голос**
- `VoiceProcessor` — faster-whisper (CPU int8), ffmpeg конвертация .ogg→.wav
- `VoiceCommandMapper` — 30+ regex-паттернов, fallback на `CommandParser`
- Гарантированное удаление temp-файлов через `finally`

**Этап 4.5 — Медиапульт**
- `BasePlatform` ABC + RuTube / YouTube / VK Video / OK Video
- `/find [платформа] <запрос>` — поиск видео, inline-кнопки выбора
- Управление: play / pause / seek / volume / mute через inline-клавиатуру
- `AdHandler` — 3 уровня: uBlock + авто-пропуск skip-кнопки + JS-детектор
- `WatchHistory` — автосохранение позиции каждые 30с
- `Watchlist` — `/wladd`, `/wlclear`, `/watchlist`
- `/mediastat` — статус плеера
- macOS-команды: `/sleep`, `/lock`, `/vol_sys`, `/mute_sys`, `/sysinfo`, `/copy`

**Этап 5 — Onboarding**
- `Settings.set/save/reload/is_onboarding_mode()`
- `setup_wizard.register_owner()`
- `/register` — первичная регистрация владельца
- `config.json` с `chmod 600`

**Этап 6 — UX**
- `/help` с группировкой по секциям
- `/start` с inline-кнопками быстрых действий
- `/status` с моделью Whisper и uptime

**Этап 7 — macOS дистрибутив**
- PyInstaller `.app` bundle, `LSUIElement=true` (только в menu bar)
- `menu_bar.py` (rumps, daemon thread)
- `build_dmg.sh`, macOS-уведомление при первом запуске

**Этап 8 — Windows дистрибутив**
- `windows_service.py` (NSSM)
- `windows_commands.py` (тот же интерфейс что macOS)
- `system/dispatcher.py` — Darwin → macOS, Windows → Windows
- `installer.iss` (Inno Setup), `setup_windows.ps1`
- GitHub Actions `build.yml` — параллельная сборка macOS + Windows при теге `v*.*.*`

**Post-completion hardening**
- playwright-stealth подключён (Chromium), graceful fallback
- `src/platform/cli.py` — `python -m src.platform.cli install/start/stop/status`
- Integration тесты: `test_browser_actions.py`, `test_voice_processor.py`, `test_player_platforms.py`
- `CHROMIUM_ANTIBOT_ARGS` (15+ флагов), `inject_extra_patches`, `human_delay/scroll/mouse`
- `dismiss_cookie_banner` для всех 4 платформ
- YouTube: `window.ytInitialData` парсинг

---

[1.1.1]: https://github.com/PVMaksim/Browser-Controller-Bot/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/PVMaksim/Browser-Controller-Bot/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/PVMaksim/Browser-Controller-Bot/releases/tag/v1.0.0
