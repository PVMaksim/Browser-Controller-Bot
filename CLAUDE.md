# CLAUDE.md — Secure Telegram Browser Controller

> Инструкция для AI-ассистента. Читай полностью перед любыми изменениями.

**Версия: 1.1.0 | Python 3.11 | aiogram 3.x | Playwright**

---

## Что это

Telegram-бот для удалённого управления браузером на Mac/Windows с iPhone/Android.
Один владелец, одна установка, никакого сервера — бот открывает только исходящее
соединение к `api.telegram.org`.

Функции: открыть URL, поиск, скриншот, медиапульт (RuTube/YouTube/VK/OK),
голосовые команды, OCR фото, управление системой (сон/блокировка/громкость).

---

## Стек

| Слой | Технология | Примечание |
|---|---|---|
| Язык | Python 3.11 | union types (`X \| Y`), match/case |
| Telegram | aiogram 3.x | Router-архитектура |
| Браузер | Playwright | Chromium / Firefox / WebKit |
| Антибот | playwright-stealth | Опциональный, graceful fallback |
| Голос | faster-whisper | Офлайн, CPU int8 |
| OCR | EasyOCR | Опциональный, ~130 МБ моделей |
| Конфиг | python-dotenv + json | .env для dev, config.json для dist |
| Пути | platformdirs | macOS: ~/Library/..., Windows: %AppData%/... |
| Логи | loguru | stdout + rotating file |
| Мониторинг | psutil | CPU/RAM/диск |
| Тесты | pytest + pytest-asyncio + pytest-mock | |
| Сборка | PyInstaller | .app (macOS), .exe (Windows) |
| macOS сервис | launchd | ~/Library/LaunchAgents/ |
| Windows сервис | NSSM | |
| CI/CD | GitHub Actions | test.yml + build.yml |

---

## Карта модулей

```
src/
├── main.py                   # Точка входа (см. «Порядок инициализации»)
├── config/
│   ├── constants.py          # ВСЕ константы. Магических чисел нет нигде.
│   ├── paths.py              # platformdirs-обёртки: get_data_dir() и др.
│   ├── settings.py           # Settings: get/require/set/save/reload
│   └── logging.py            # loguru setup
├── browser/
│   ├── engine.py             # BrowserEngine: start/stop/open_url/screenshot/search
│   ├── idle_watcher.py       # Авто-стоп: idle_watcher.reset() при каждой команде
│   ├── antibot.py            # CHROMIUM_ANTIBOT_ARGS, inject_extra_patches, UA re-export
│   ├── stealth.py            # Per-browser StealthConfig + UA pools + JS patches
│   └── watchdog.py           # Probe 60с → stop+start при зависании
├── voice/
│   ├── processor.py          # ffmpeg .ogg→.wav + faster-whisper → text
│   └── command_mapper.py     # 30+ regex-паттернов → (command, arg)
├── ocr/
│   └── core.py               # OCRProcessor (lazy EasyOCR), process_image_search
├── player/
│   ├── controller.py         # PlayerController: search×retry, open_video, play/pause/…
│   ├── state.py              # PlayerState dataclass
│   ├── keyboards.py          # Inline-клавиатуры медиапульта
│   ├── ad_handler.py         # 3-уровневая защита от рекламы
│   ├── watch_history.py      # Сохранение позиции каждые 30с
│   ├── watchlist.py          # «Посмотреть позже»
│   └── platforms/
│       ├── base.py           # BasePlatform ABC + SearchResult
│       ├── rutube.py
│       ├── youtube.py
│       ├── vk_video.py
│       └── ok_video.py
├── system/
│   ├── dispatcher.py         # get_system_commands() → macOS / Windows
│   ├── macos_commands.py     # sleep / lock / vol_sys / mute_sys / sysinfo / copy
│   └── windows_commands.py   # тот же интерфейс
├── handlers/
│   ├── commands.py           # /open /search /shot /close /play /pause /status /stop /help
│   ├── player.py             # /find /mediastat /watchlist /wladd /wlclear + callbacks
│   ├── system_commands.py    # /sleep /lock /vol_sys /mute_sys /sysinfo /copy
│   ├── voice.py              # Голосовые сообщения
│   ├── photo.py              # Фото → OCR → URL поиска; /ocr
│   └── onboarding.py         # /start /register (только onboarding-режим)
├── middlewares/
│   ├── access_control.py     # check_access(user_id) — whitelist
│   ├── rate_limiter.py       # Sliding window 10 cmd / 10с
│   └── error_handler.py      # notify_owner_on_error → traceback в Telegram
├── onboarding/
│   └── setup_wizard.py       # register_owner(user_id, settings)
├── platform/
│   ├── service_manager.py    # get_service_manager() → launchd / NSSM
│   ├── launchd.py            # macOS LaunchAgent
│   ├── windows_service.py    # NSSM wrapper
│   ├── menu_bar.py           # rumps daemon thread (macOS)
│   └── cli.py                # python -m src.platform.cli install/start/stop/status
└── utils/
    ├── validators.py         # validate_url, normalize_url, sanitize_search_query
    ├── sanitize.py           # sanitize_caption, sanitize_text
    └── system_info.py        # format_status_message, get_uptime_str
```

---

## Порядок инициализации (main.py)

```python
Settings()                          # 1. Загрузка конфига
setup_logging()                     # 2. loguru
Bot() + Dispatcher()                # 3. aiogram
BrowserEngine()                     # 4. Playwright (не запущен ещё)
IdleWatcher()                       # 5. Создан, не запущен
VoiceProcessor()                    # 6. Lazy — Whisper загрузится при первом голосе
PlayerController()                  # 7. Медиапульт
OCRProcessor()                      # 8. Lazy — EasyOCR загрузится при первом фото

dp.message.middleware(RateLimiterMiddleware())  # 9. ПЕРВЫЙ — до всех роутеров

# 10. Роутеры в строгом порядке:
dp.include_router(get_onboarding_router(...))   # onboarding — ПЕРВЫЙ
dp.include_router(get_command_router(...))       # /open /search /shot ...
dp.include_router(get_player_router(...))        # /find /mediastat ...
dp.include_router(get_system_router(...))        # /sleep /lock ...
dp.include_router(get_photo_router(...))         # photo handler
dp.include_router(get_voice_router(...))         # voice — ПОСЛЕДНИЙ

BrowserWatchdog().start()  # 11. Только если NOT is_onboarding
await dp.start_polling()   # 12. Блокирующий запуск
```

**Почему onboarding первый:** в onboarding-режиме (`ALLOWED_USER_ID` не задан)
бот должен принять `/register` от любого пользователя. Остальные роутеры отклоняют
неавторизованных через `_guard()`.

---

## Onboarding flow

```
1. Первый запуск → settings.is_onboarding_mode() == True
                   (ALLOWED_USER_ID не задан в config.json)
2. Пользователь → /register
3. setup_wizard.register_owner(user_id, settings)
   → settings.set("ALLOWED_USER_ID", user_id)
   → settings.save()              ← атомарный .json.tmp → rename
4. loop.stop() → launchd/NSSM перезапускает процесс
5. Следующий старт → is_onboarding_mode() == False
6. Все роутеры работают, watchdog запускается
```

---

## Guard pattern (во всех хендлерах)

```python
async def _guard(message: Message) -> bool:
    if not message.from_user:
        return False
    return await check_access(message.from_user.id, bot, settings)

@r.message(Command("mycommand"))
async def cmd_something(message: Message) -> None:
    if not await _guard(message):
        return
    # ... логика
```

`_guard` определён внутри `get_*_router()` — замыкание над `bot` и `settings`.

---

## Как добавить новую команду

1. **Handler** — добавить в нужный `src/handlers/*.py`:
   ```python
   @r.message(Command("mycommand"))
   async def cmd_my(message: Message) -> None:
       if not await _guard(message):
           return
       # логика
   ```

2. **idle_watcher** — сбросить таймер idle если команда обращается к браузеру:
   ```python
   idle_watcher.reset()
   ```

3. **constants.py** — добавить любые числа/строки (не хардкодить в коде).

4. **/help** — добавить строку в `help_text` в `src/handlers/commands.py`.
   ⚠️ `test_help_completeness.py` упадёт автоматически если забыть этот шаг —
   он парсит все `Command(...)` через AST и проверяет наличие в тексте `/help`.

---

## Как добавить новую медиаплатформу

1. Создать `src/player/platforms/myplatform.py`:
   ```python
   class MyPlatform(BasePlatform):
       async def search(self, page, query) -> list[SearchResult]: ...
       async def open_video(self, page, url) -> None: ...
   ```
   Обязательно вызывать `dismiss_cookie_banner` и `human_delay` в `search()` и `open_video()`.

2. Зарегистрировать в `src/player/controller.py`:
   ```python
   _PLATFORM_REGISTRY["myplatform"] = MyPlatform
   ```

3. Добавить псевдоним в `src/voice/command_mapper.py`:
   ```python
   "мойсайт": "myplatform",
   ```

4. Добавить в список платформ в `/help` (`commands.py`).

---

## Антибот-слой (порядок применения)

| # | Что | Где вызывается |
|---|---|---|
| 1 | `CHROMIUM_ANTIBOT_ARGS` (15+ флагов) | `engine.start()` для Chromium |
| 2 | `inject_extra_patches(page)` (Chromium JS) | `engine._setup_page()` |
| &nbsp; | ИЛИ `get_extra_patches(browser_type)` (Firefox/WebKit JS) | `engine._setup_page()` |
| 3 | `playwright-stealth` с per-browser `StealthConfig` | `stealth.apply(page, browser_type)` |
| 4 | `human_delay()` + `human_scroll()` + `human_move_mouse()` | В методах каждой платформы |
| 5 | `dismiss_cookie_banner(page, platform)` | `search()` и `open_video()` каждой платформы |

**Ключевое правило stealth:** НЕ применять `chrome_app`, `chrome_runtime`,
`navigator_plugins`, `webgl_vendor` к Firefox и WebKit — это делает их
fingerprint более подозрительным, а не менее.

**UA-пулы в `stealth._UA_POOLS`:**
- `chromium` → Chrome 120–124 (macOS Intel, macOS M-chip, Windows)
- `firefox` → Firefox 121–125 (macOS, Windows)
- `webkit` → Safari 17.x (macOS Intel, macOS M-chip)

UA фиксируется один раз в `engine.start()` через `session_ua = _stealth.get_user_agent(browser_type)`.
Менять UA в середине сессии нельзя.

---

## Медиаплатформы — детали

**Обязательный интерфейс `BasePlatform`:**
```python
search(page, query)  → list[SearchResult]   # abstract
open_video(page, url) → None                # abstract
play / pause / seek_relative / seek_absolute
set_volume / toggle_mute / get_state / has_video  # с дефолтной JS-реализацией
```

**Как платформы парсят результаты:**
- YouTube → `window.ytInitialData` (JSON, надёжнее DOM) → DOM как fallback
- RuTube → `window.__INITIAL_SSR_STATE__`
- VK / OK → ожидание React SPA + CSS-селекторы карточек

**Retry в `PlayerController.search()`:**
0 результатов — это не ошибка, платформа могла подвиснуть.
До `SEARCH_RETRY_COUNT=2` повторных попыток с паузой `SEARCH_RETRY_DELAY_SEC=3.0`.

---

## Settings API

```python
settings.get("KEY")            # → Any | None
settings.get("KEY", default)   # → Any
settings.require("KEY")        # → str, raises ValueError если нет
settings.set("KEY", value)     # изменить в памяти
settings.save()                # атомарно: .json.tmp → rename
settings.reload()              # перечитать с диска
settings.is_onboarding_mode()  # → bool (ALLOWED_USER_ID не задан)
```

Никогда не читать `.env` напрямую — только через `settings`.

---

## Rate limiting

`RateLimiterMiddleware` стоит первым в `dp.message.middleware(...)`.
Константы: `RATE_LIMIT_MAX_CALLS=10`, `RATE_LIMIT_WINDOW_SEC=10.0`.
**Non-Message события (callback_query) не ограничиваются.**
При превышении — тихий drop + предупреждение пользователю раз в 30с.

---

## Browser Watchdog

Запускается после инициализации браузера, **не в onboarding-режиме**.
Probe каждые `WATCHDOG_CHECK_INTERVAL_SEC=60` сек:
```python
await page.evaluate("() => typeof window")  # timeout: 5с
```
При зависании: `browser.stop()` → `browser.start()` → уведомление владельцу.
Максимум `WATCHDOG_MAX_RESTARTS=5`, затем требует ручного `/stop confirm`.

---

## Тесты

```
tests/
  unit/   (27 файлов)               integration/   (3 файла)
```

```bash
pytest tests/unit/ -v
pytest tests/ --cov=src --cov-fail-under=70
```

**`test_help_completeness.py`** — архитектурный guard:
- Парсит все `Command("…")` регистрации через AST
- Проверяет что каждая команда упомянута в тексте `/help`
- **Падает автоматически** если добавить команду без документирования

---

## Константы — группы

```python
# Telegram message limits     TELEGRAM_MAX_MESSAGE_LENGTH, ...
# Browser                     DEFAULT_BROWSER_TYPE, SEARCH_ENGINES, ...
# Security                    DEFAULT_IDLE_TIMEOUT_MINUTES, ...
# Voice                       DEFAULT_WHISPER_MODEL, VOICE_TMP_PREFIX, ...
# Player                      DEFAULT_SEARCH_RESULTS_LIMIT, SEEK_SHORT_SEC, ...
# Watchlist                   MAX_WATCHLIST_ITEMS
# URL schemes                 ALLOWED_URL_SCHEMES, BLOCKED_URL_SCHEMES
# /stop                       STOP_CONFIRM_SUFFIX = "confirm"
# OCR                         OCR_LANGUAGES, OCR_MIN_CONFIDENCE, ...
# Rate limiting               RATE_LIMIT_MAX_CALLS, RATE_LIMIT_WINDOW_SEC, ...
# Watchdog                    WATCHDOG_CHECK_INTERVAL_SEC, WATCHDOG_MAX_RESTARTS, ...
# Search retry                SEARCH_RETRY_COUNT, SEARCH_RETRY_DELAY_SEC
```

---

## .env / config.json — все переменные

| Переменная | Default | Описание |
|---|---|---|
| `BOT_TOKEN` | — | Токен от @BotFather, обязательный |
| `ALLOWED_USER_ID` | — | Задаётся через /register, не вручную |
| `WHISPER_MODEL` | `base` | tiny/base/small/medium/large |
| `DEFAULT_MEDIA_PLATFORM` | `rutube` | rutube/youtube/vk/ok |
| `BROWSER_TYPE` | `chromium` | chromium/firefox/webkit |
| `BROWSER_HEADLESS` | `false` | Headless не поддерживается платформами |
| `LOG_LEVEL` | `INFO` | DEBUG/INFO/WARNING |
| `SEARCH_ENGINE` | `google` | google/duckduckgo |
| `SEARCH_RESULTS_LIMIT` | `5` | 1–10 |
| `IDLE_TIMEOUT_MINUTES` | `10` | Авто-закрытие браузера |
| `POSITION_SAVE_INTERVAL_SEC` | `30` | Как часто сохранять позицию просмотра |

---

## Типичные ошибки AI в этом проекте

| Ошибка | Правильно |
|---|---|
| Хардкодить путь `"~/.config/..."` | `get_data_dir()` из `src/config/paths.py` |
| Добавить магическое число | Константу в `src/config/constants.py` |
| `stealth_async(page)` без конфига | `stealth.apply(page, browser_type)` |
| Применить `chrome_app=True` для Firefox | `_make_config("firefox")` отключает это |
| Менять UA в середине сессии | UA задаётся один раз в `engine.start()` |
| `settings.get("ALLOWED_USER_ID")` напрямую | `check_access(user_id, bot, settings)` |
| Забыть `idle_watcher.reset()` | Вызывать после каждой браузерной операции |
| Добавить команду без строки в `/help` | Тест `test_help_completeness` сломается |
| Добавить платформу без псевдонима | `command_mapper.py` → `_PLATFORM_ALIASES` |
| Запустить watchdog в onboarding | `if not is_onboarding: watchdog.start()` |

---

## Команды

```bash
# Запуск
python src/main.py

# Тесты
pytest tests/unit/ -v
pytest tests/ --cov=src --cov-fail-under=70

# Сервис
python -m src.platform.cli install
python -m src.platform.cli start / stop / status

# Релиз
git tag v1.1.0 && git push origin --tags
# → GitHub Actions: test.yml проверяет, build.yml собирает .dmg и .exe
```
