# src/config/constants.py
"""
All project-wide constants.
Нет магических чисел и строк нигде в коде — только ссылки на этот файл.
"""

APP_NAME = "SecureBrowserBot"
APP_VERSION = "1.1.0"

# Telegram message limits
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_CAPTION_LENGTH = 1024

# Browser
DEFAULT_BROWSER_TYPE = "chromium"
DEFAULT_BROWSER_HEADLESS = False
DEFAULT_SEARCH_ENGINE = "google"
SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
}

# Security
DEFAULT_IDLE_TIMEOUT_MINUTES = 10
DEFAULT_STOP_CONFIRM_TIMEOUT_SECONDS = 30

# Voice
DEFAULT_WHISPER_MODEL = "base"
WHISPER_SUPPORTED_MODELS = ("tiny", "base", "small", "medium", "large")
VOICE_TMP_PREFIX = "voice_"
VOICE_TMP_SUFFIX = ".wav"

# Logging
DEFAULT_LOG_LEVEL = "INFO"
LOG_ROTATION_SIZE = "10 MB"
LOG_RETENTION_DAYS = "14 days"
LOG_COMPRESSION = "gz"

# Player (Stage 4.5)
DEFAULT_MEDIA_PLATFORM = "rutube"
DEFAULT_SEARCH_RESULTS_LIMIT = 5
MAX_SEARCH_RESULTS_LIMIT = 10
DEFAULT_PLAYER_SEEK_SHORT_SEC = 30
DEFAULT_PLAYER_SEEK_LONG_SEC = 300
DEFAULT_POSITION_SAVE_INTERVAL_SEC = 30
DEFAULT_MAX_HISTORY_ITEMS = 50

# Watchlist
MAX_WATCHLIST_ITEMS = 100

# Allowed URL schemes
ALLOWED_URL_SCHEMES = ("http://", "https://")
BLOCKED_URL_SCHEMES = ("javascript:", "data:", "ftp:", "file:", "vbscript:")

# /stop confirmation text
STOP_CONFIRM_SUFFIX = "confirm"

# Error notification: max traceback length sent to Telegram
ERROR_TRACEBACK_MAX_LENGTH = 3000

# Rate limiting (middlewares/rate_limiter.py)
RATE_LIMIT_MAX_CALLS = 10           # Максимум команд за окно
RATE_LIMIT_WINDOW_SEC = 10.0        # Ширина скользящего окна (секунды)
RATE_LIMIT_NOTIFY_COOLDOWN_SEC = 30.0  # Не чаще раза в 30 сек предупреждаем

# Browser watchdog (browser/watchdog.py)
WATCHDOG_CHECK_INTERVAL_SEC = 60    # Проверять браузер каждые 60 секунд
WATCHDOG_PROBE_TIMEOUT_MS = 5000    # Таймаут JS-пробы (5 сек)
WATCHDOG_MAX_RESTARTS = 5           # Максимум автоматических перезапусков
