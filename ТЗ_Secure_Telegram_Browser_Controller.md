# Техническое задание
# Проект: Secure Telegram Browser Controller for macOS
**Версия:** 2.0 (финальная, с учётом архитектурного ревью)
**Дата:** 2026-03-09
**Статус:** Утверждено

---

## 1. Общие сведения

| Поле | Значение |
|---|---|
| **Цель** | Создание защищённого Telegram-бота для удалённого управления браузером на конкретном Mac через текстовые и голосовые команды |
| **Платформа исполнения** | macOS (локально, нативный процесс) |
| **Язык разработки** | Python 3.10+ |
| **Приоритет** | Безопасность > Удобство > Функциональность |
| **Docker** | ❌ Не используется — бот управляет браузером хост-машины. Контейнеризация несовместима с этой архитектурой. Запуск через `launchd` (macOS native) |

> **Обоснование отказа от Docker:** Playwright должен управлять реальным браузером на экране Mac. Контейнер изолирован от графической подсистемы хоста и не имеет доступа к дисплею. Для данного проекта нативный запуск — единственно корректный выбор.

---

## 2. Архитектура системы

Система — монолитное приложение, работающее локально на машине пользователя без входящих сетевых соединений.

```
┌─────────────────────────────────────────────────────────┐
│                     macOS (хост)                        │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │   Telegram   │◄──►│  Bot Process │                   │
│  │  Interface   │    │  (launchd)   │                   │
│  │  (aiogram 3) │    └──────┬───────┘                   │
│  └──────────────┘           │                           │
│                    ┌────────▼────────┐                  │
│                    │ Command Parser  │                  │
│                    └────────┬────────┘                  │
│            ┌───────────────┼──────────────┐             │
│     ┌──────▼──────┐ ┌──────▼──────┐ ┌────▼──────┐       │
│     │   Browser   │ │    Voice    │ │    OCR    │       │
│     │   Engine    │ │  Processor  │ │   Core    │       │
│     │ (Playwright)│ │  (Whisper)  │ │ (Future)  │       │
│     └─────────────┘ └─────────────┘ └───────────┘       │
└─────────────────────────────────────────────────────────┘
         │ исходящие соединения только к Telegram API
```

### Модули

| Модуль | Описание |
|---|---|
| **Telegram Interface** | Приём сообщений, проверка прав доступа, отправка ответов |
| **Command Parser** | Преобразование текста (из сообщения или расшифровки голоса) в команды |
| **Browser Engine** | Выполнение действий в браузере через Playwright |
| **Voice Processor** | Локальная расшифровка голосовых сообщений через faster-whisper |
| **OCR Core** | Заготовка под распознавание текста на скриншотах (реализуется в Этапе 4) |

---

## 3. Требования к безопасности

### 3.1. White-list доступ (обязательно)

- Бот реагирует **только на один** заранее заданный Telegram User ID (`ALLOWED_USER_ID` в `.env`)
- Все остальные запросы — логируются как попытка несанкционированного доступа и отправляют алерт владельцу
- Никаких паролей в чате не требуется — идентификация по Telegram ID

```python
# src/middlewares/access_control.py
async def check_access(user_id: int, bot: Bot) -> bool:
    """Verify user is authorized. Send alert to owner on unauthorized access."""
    allowed_id = int(os.getenv("ALLOWED_USER_ID"))
    if user_id != allowed_id:
        # Алертим владельца об попытке несанкционированного доступа
        await bot.send_message(
            allowed_id,
            f"🚨 <b>Попытка доступа</b>\nUser ID: <code>{user_id}</code>",
            parse_mode="HTML"
        )
        return False
    return True
```

### 3.2. Хранение секретов

- `BOT_TOKEN` и все чувствительные данные — **только в `.env`**
- `.env` добавлен в `.gitignore`
- Права на файл: `chmod 600 .env` (только владелец читает и пишет)
- В репозиторий коммитится только `.env.example` с фиктивными значениями и комментариями

### 3.3. Сетевая безопасность

- Приложение **не открывает ни одного входящего порта**
- Исходящие соединения: только к `api.telegram.org`
- Порт базы данных: БД не используется в данном проекте

### 3.4. Защита данных

- Голосовые сообщения скачиваются во временную папку `tmp/`, обрабатываются и **немедленно удаляются** после расшифровки
- Логи хранятся локально в `logs/`, **не отправляются** в облако
- Браузер запускается в **изолированном профиле** (обязательное требование, не опция)

### 3.5. Защита от инъекций

- URL, передаваемые в браузер, проходят валидацию схемы (`http://` или `https://` — и только они)
- Текст голосовых команд санируется перед парсингом

### 3.6. Подтверждение критических команд

Команда `/stop` требует двухшагового подтверждения:

```
Пользователь: /stop
Бот: ⚠️ Подтвердить остановку? Отправьте /stop confirm в течение 30 секунд.
Пользователь: /stop confirm
Бот: 🛑 Остановка...
```

---

## 4. Функциональные требования

### 4.1. Текстовые команды

| Команда | Описание |
|---|---|
| `/open <url>` | Открыть URL в браузере (с валидацией схемы) |
| `/search <query>` | Поиск в Google (или DuckDuckGo — задаётся в `.env`) |
| `/shot` | Скриншот активной вкладки → отправить в Telegram |
| `/close` | Закрыть текущую вкладку |
| `/status` | Статус (онлайн, текущий URL, версия бота) |
| `/stop` | Остановка бота (с двухшаговым подтверждением) |

### 4.2. Голосовое управление

При получении голосового сообщения (`.ogg` / `.wav`):

1. Файл загружается в `tmp/`
2. Конвертируется через `ffmpeg` в формат, совместимый с Whisper
3. Расшифровывается локальной моделью faster-whisper (без отправки аудио в интернет)
4. Текст анализируется Command Parser'ом
5. Временный файл **немедленно удаляется**

**Примеры сопоставлений:**

| Голосовая фраза | Команда |
|---|---|
| «Открой ютуб» | `/open youtube.com` |
| «Найди рецепт борща» | `/search рецепт борща` |
| «Сделай скриншот» | `/shot` |
| «Закрой вкладку» | `/close` |

### 4.3. Уведомления об ошибках (обязательно)

**Любое необработанное исключение** отправляет уведомление владельцу в Telegram:

```python
# src/middlewares/error_handler.py
import traceback
from aiogram import Bot

async def notify_owner_on_error(bot: Bot, error: Exception, context: str = "") -> None:
    """Send error traceback to developer via Telegram."""
    # Уведомляем разработчика о необработанной ошибке с полным трейсбеком
    owner_id = int(os.getenv("ALLOWED_USER_ID"))
    text = (
        f"🔴 <b>Ошибка бота</b>\n"
        f"<code>{context}</code>\n\n"
        f"<pre>{traceback.format_exc()[:3000]}</pre>"
    )
    await bot.send_message(owner_id, text, parse_mode="HTML")
```

### 4.4. Таймаут бездействия браузера

- Если браузер открыт ботом и **не было команд 10 минут** — вкладка автоматически закрывается
- Значение таймаута задаётся через `IDLE_TIMEOUT_MINUTES` в `.env`
- Перед закрытием — уведомление в Telegram: «⏱ Вкладка закрыта по таймауту бездействия»

### 4.5. Изолированный профиль браузера (обязательно)

Бот запускает браузер **не в основном профиле пользователя**, а в отдельном изолированном профиле. Это защищает сохранённые пароли, куки и банковские сессии.

```python
# src/browser/engine.py
async def launch_browser(playwright) -> tuple:
    """Launch browser in isolated profile to protect main user session."""
    browser = await playwright.chromium.launch_persistent_context(
        user_data_dir="/tmp/bot_browser_profile",
        headless=False  # Браузер виден на экране Mac
    )
    return browser
```

### 4.6. Заготовка OCR (Этап 4)

В коде выделена изолированная функция — реализуется в будущем без переписывания ядра:

```python
# src/ocr/core.py
async def process_image_search(image_path: str) -> str | None:
    """
    Extract text from image and search for movie/content title.
    Returns search URL or None if extraction fails.
    
    Будущая реализация: EasyOCR или PaddleOCR (~2 ГБ зависимостей).
    """
    # TODO: Этап 4 — подключить OCR-библиотеку
    raise NotImplementedError("OCR module not yet implemented")
```

---

## 5. Технический стек

| Компонент | Библиотека / Инструмент | Версия |
|---|---|---|
| Язык | Python | 3.10+ |
| Telegram-бот | aiogram | 3.x |
| Автоматизация браузера | playwright | latest |
| Распознавание речи | faster-whisper | latest |
| Конвертация аудио | ffmpeg | (brew install ffmpeg) |
| Конфигурация | python-dotenv | latest |
| Логирование | loguru | latest |
| Запуск как сервис | launchd (macOS native) | — |

---

## 6. Конфигурация (`.env.example`)

```env
# === Telegram ===
BOT_TOKEN=                          # Токен бота от @BotFather
ALLOWED_USER_ID=                    # Твой личный Telegram ID (единственный разрешённый)

# === Браузер ===
BROWSER_TYPE=chromium               # chromium | firefox | webkit
BROWSER_HEADLESS=false              # false = браузер виден на экране Mac
BROWSER_PROFILE_DIR=/tmp/bot_browser_profile  # Изолированный профиль

# === Голос ===
WHISPER_MODEL=base                  # base (быстро) | small | medium (точнее, больше RAM)

# === Поиск ===
SEARCH_ENGINE=google                # google | duckduckgo

# === Безопасность ===
IDLE_TIMEOUT_MINUTES=10             # Закрыть браузер после N минут бездействия
STOP_CONFIRM_TIMEOUT_SECONDS=30     # Таймаут подтверждения команды /stop

# === Логи ===
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR
LOG_DIR=logs                        # Папка для лог-файлов (добавить в .gitignore)
```

---

## 7. Логирование

Loguru настраивается на вывод **и в stdout, и в файл** с ротацией:

```python
# src/config/logging.py
from loguru import logger
import os

def setup_logging() -> None:
    """Configure logging to stdout and rotating file."""
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Stdout — для наблюдения в реальном времени
    logger.add(sys.stdout, level=os.getenv("LOG_LEVEL", "INFO"))
    
    # Файл — с ротацией по размеру, хранение 7 дней, архивирование
    logger.add(
        f"{log_dir}/bot.log",
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        level="DEBUG"
    )
```

**Папка `logs/` добавляется в `.gitignore`.**

---

## 8. Структура проекта

```text
secure-browser-bot/
├── src/
│   ├── main.py                     # Точка входа, регистрация хендлеров
│   ├── config/
│   │   ├── settings.py             # Загрузка .env через python-dotenv
│   │   └── logging.py              # Настройка loguru
│   ├── handlers/
│   │   ├── commands.py             # /open, /search, /shot, /close, /status, /stop
│   │   └── voice.py                # Обработка голосовых сообщений
│   ├── browser/
│   │   ├── engine.py               # Playwright: запуск, изолированный профиль
│   │   ├── actions.py              # open_url, take_screenshot, close_tab
│   │   └── idle_watcher.py         # Таймаут бездействия
│   ├── voice/
│   │   ├── processor.py            # Загрузка, конвертация, расшифровка, удаление
│   │   └── command_mapper.py       # Текст → команда бота
│   ├── ocr/
│   │   └── core.py                 # Заглушка для будущего OCR-модуля
│   ├── middlewares/
│   │   ├── access_control.py       # White-list по Telegram ID
│   │   └── error_handler.py        # Глобальный перехват ошибок → Telegram
│   └── utils/
│       └── validators.py           # Валидация URL и входных данных
├── scripts/
│   ├── setup_macos.sh              # Установка зависимостей, настройка launchd
│   └── health_check.sh             # Проверка состояния бота
├── tests/
│   ├── test_access_control.py
│   ├── test_command_parser.py
│   └── test_url_validator.py
├── docs/
│   └── architecture.md             # Описание модулей и потоков данных
├── tmp/                            # Временные файлы (в .gitignore)
├── logs/                           # Лог-файлы (в .gitignore)
├── com.user.secure-browser-bot.plist  # Конфиг launchd для автозапуска
├── .env.example                    # Шаблон конфига — коммитится в Git
├── .env                            # Реальные значения — НИКОГДА не коммитить
├── .gitignore
├── requirements.txt
├── CLAUDE.md
├── MEMORY.md
└── README.md
```

---

## 9. Автозапуск на macOS (launchd)

Вместо Docker используется нативный механизм macOS — `launchd`:

```xml
<!-- com.user.secure-browser-bot.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.secure-browser-bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/username/projects/secure-browser-bot/src/main.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ENV_FILE</key>
        <string>/Users/username/projects/secure-browser-bot/.env</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/username/projects/secure-browser-bot/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/username/projects/secure-browser-bot/logs/launchd_error.log</string>
</dict>
</plist>
```

**Управление сервисом:**
```bash
# Установить и запустить
launchctl load ~/Library/LaunchAgents/com.user.secure-browser-bot.plist

# Остановить
launchctl unload ~/Library/LaunchAgents/com.user.secure-browser-bot.plist

# Проверить статус
launchctl list | grep secure-browser-bot
```

---

## 10. Настройка macOS (`scripts/setup_macos.sh`)

```bash
#!/bin/bash
# Первичная настройка macOS для работы бота
set -euo pipefail

echo "📦 Установка зависимостей..."
brew install ffmpeg python@3.11

echo "🐍 Установка Python-зависимостей..."
pip3 install -r requirements.txt
playwright install chromium

echo "⚙️ Проверка ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg не найден. Установи: brew install ffmpeg"
    exit 1
fi
echo "✅ ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

echo "🔒 Настройка прав на .env..."
chmod 600 .env

echo "☕ Запрет спящего режима при работе от питания..."
sudo pmset -c sleep 0
sudo pmset -c disksleep 0
echo "✅ Спящий режим отключён при питании от сети"

echo "🚀 Установка launchd-сервиса..."
cp com.user.secure-browser-bot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.secure-browser-bot.plist

echo "✅ Настройка завершена"
```

---

## 11. Чеклист безопасности (перед каждым запуском)

- [ ] `.env` добавлен в `.gitignore`
- [ ] В ни одном закоммиченном файле нет токенов или ID
- [ ] `.env.example` содержит все ключи с фиктивными значениями и комментариями
- [ ] `chmod 600 .env` выполнен
- [ ] `ALLOWED_USER_ID` задан корректно
- [ ] Проверена валидация URL (тест с `javascript:` схемой — должна отклоняться)
- [ ] Папки `tmp/` и `logs/` добавлены в `.gitignore`
- [ ] Изолированный профиль браузера активен (`BROWSER_PROFILE_DIR` ≠ основной профиль Chrome)
- [ ] ffmpeg установлен: `ffmpeg -version`
- [ ] Тестовое голосовое сообщение обработано и файл удалён из `tmp/`

---

## 12. План реализации (Roadmap)

### Этап 1 — Базовый (MVP)
- Настройка окружения, `setup_macos.sh`
- Запуск бота через launchd
- White-list по Telegram ID + алерты о попытках доступа
- Команды `/open`, `/status`, `/stop` с подтверждением
- Глобальный error handler → уведомление в Telegram

### Этап 2 — Браузер
- Изолированный профиль Playwright
- Команды `/search`, `/shot`, `/close`
- Таймаут бездействия (`IDLE_TIMEOUT_MINUTES`)
- Валидация URL

### Этап 3 — Голос
- Интеграция faster-whisper
- Конвертация `.ogg` через ffmpeg
- Command Parser для голосовых команд
- Гарантированное удаление временных файлов

### Этап 4 — OCR (отдельный спринт)
- Подключение EasyOCR или PaddleOCR (~2 ГБ моделей)
- Реализация `process_image_search()` без изменений остального кода
- Команда: отправить фото → получить ссылку для поиска

---

## 13. Вопросы, закрытые архитектурным решением

| Вопрос из v1.0 ТЗ | Решение |
|---|---|
| Держать ли Mac включённым? | `setup_macos.sh` отключает сон при питании от сети |
| Модель Whisper — base или medium? | `WHISPER_MODEL=base` по умолчанию, переключается в `.env` без изменения кода |
| Какой браузер? | Chromium по умолчанию (`BROWSER_TYPE=chromium`), переключается в `.env` |
| Чистый браузер или с сессиями? | Изолированный профиль — чистый и безопасный (обязательное требование) |
| OCR — устанавливать зависимости сейчас? | Нет. Заглушка в коде, реальная реализация — в Этапе 4 |

---

*ТЗ версии 2.0 — финальная редакция с учётом архитектурного ревью. Все предложения из ревью v1.0 интегрированы в основные требования.*


