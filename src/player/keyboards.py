# src/player/keyboards.py
"""
Inline keyboard builders for the media remote control and search results.
Все callback_data следуют схеме "player:<action>[:<value>]".
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.player.platforms.base import SearchResult

# Максимальная длина текста кнопки с результатом поиска
_RESULT_TITLE_MAX = 40


def build_player_keyboard(platform: str) -> InlineKeyboardMarkup:
    """
    Build full media remote control keyboard.
    Показывает платформу в заголовке через emoji — пользователь видит контекст.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Играть",   callback_data="player:play"),
            InlineKeyboardButton(text="⏸ Пауза",    callback_data="player:pause"),
        ],
        [
            InlineKeyboardButton(text="⏪ −30с",     callback_data="player:seek:-30"),
            InlineKeyboardButton(text="⏩ +30с",     callback_data="player:seek:+30"),
        ],
        [
            InlineKeyboardButton(text="⏪ −5мин",    callback_data="player:seek:-300"),
            InlineKeyboardButton(text="⏩ +5мин",    callback_data="player:seek:+300"),
        ],
        [
            InlineKeyboardButton(text="🔉 Тише",     callback_data="player:vol:-20"),
            InlineKeyboardButton(text="🔊 Громче",   callback_data="player:vol:+20"),
        ],
        [
            InlineKeyboardButton(text="🔇 Тишина",   callback_data="player:mute"),
            InlineKeyboardButton(text="📊 Статус",   callback_data="player:status"),
        ],
        [
            InlineKeyboardButton(text="⛔ Закрыть плеер", callback_data="player:close"),
        ],
    ])


def build_search_results_keyboard(results: list[SearchResult]) -> InlineKeyboardMarkup:
    """
    Build numbered list keyboard for search results (max 5 items).
    Длинные названия обрезаются с многоточием для аккуратного вида.
    """
    buttons = []
    for i, result in enumerate(results[:5], start=1):
        title = result.title
        if len(title) > _RESULT_TITLE_MAX:
            title = title[:_RESULT_TITLE_MAX] + "…"
        label = f"{i}. {title}"
        if result.duration:
            label += f" · {result.duration}"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"player:open:{i}")
        ])
    # Кнопка сохранения в watchlist рядом с каждым результатом убрана для простоты —
    # отдельная кнопка /watchlist add добавляется в Этапе 5 UX-полировки
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_resume_keyboard(position_str: str) -> InlineKeyboardMarkup:
    """
    Build 'resume or restart' keyboard for 'continue watching' prompt.
    Показывается когда пользователь ищет видео, которое уже смотрел.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"▶️ Продолжить с {position_str}",
                callback_data="player:resume",
            ),
            InlineKeyboardButton(
                text="🔄 Начать сначала",
                callback_data="player:restart",
            ),
        ],
        [
            InlineKeyboardButton(text="🔍 Новый поиск", callback_data="player:newsearch"),
        ],
    ])


def build_watchlist_item_keyboard(url: str) -> InlineKeyboardMarkup:
    """Keyboard under each watchlist item: watch or delete."""
    # url используем как часть callback_data — кодируем в base64 для безопасности
    import base64
    encoded = base64.urlsafe_b64encode(url.encode()).decode()[:40]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Смотреть", callback_data=f"wl:watch:{encoded}"),
            InlineKeyboardButton(text="🗑 Удалить",  callback_data=f"wl:del:{encoded}"),
        ],
    ])
