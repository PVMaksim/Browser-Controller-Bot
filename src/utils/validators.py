# src/utils/validators.py
"""
Input validation: URLs, user text, voice command output.
Защита от инъекций — первый рубеж обороны перед браузером.
"""

from urllib.parse import urlparse

from src.config.constants import ALLOWED_URL_SCHEMES, BLOCKED_URL_SCHEMES


def validate_url(url: str) -> bool:
    """
    Validate URL before passing to browser.
    Блокирует javascript:, data:, ftp: и другие опасные схемы.

    Returns True for valid http/https URLs, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    url_lower = url.lower().strip()

    # Явно блокируем опасные схемы
    for blocked in BLOCKED_URL_SCHEMES:
        if url_lower.startswith(blocked):
            return False

    # Разрешаем только http и https
    if not any(url_lower.startswith(scheme) for scheme in ALLOWED_URL_SCHEMES):
        return False

    # Дополнительная проверка через urlparse
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def sanitize_search_query(query: str) -> str:
    """
    Sanitize user search query before use.
    Удаляет лишние пробелы, ограничивает длину.
    """
    if not query:
        return ""
    # Удаляем лишние пробелы, ограничиваем до 500 символов
    return " ".join(query.strip().split())[:500]


def normalize_url(url: str) -> str:
    """
    Normalize URL: add https:// if scheme is missing.
    Используется для удобного ввода типа 'youtube.com'.
    """
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url
