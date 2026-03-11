# src/player/state.py
"""
Current media player state — single source of truth for the player module.
Хранится в памяти: сбрасывается при перезапуске бота, не требует БД.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlayerState:
    """
    Tracks everything about the current playback session.
    Обновляется контроллером при каждой команде и каждые 30 сек автосохранением.
    """

    is_active: bool = False
    platform: str | None = None        # "rutube" | "youtube" | "vk" | "ok"
    title: str | None = None
    url: str | None = None
    position_seconds: int = 0
    duration_seconds: int = 0
    volume: int = 100
    is_paused: bool = True
    is_muted: bool = False
    # Результаты последнего поиска — хранятся для выбора по номеру кнопки
    search_results: list = field(default_factory=list)
    last_command_at: datetime | None = None

    def reset(self) -> None:
        """Clear all playback state (called when player is closed)."""
        self.is_active = False
        self.platform = None
        self.title = None
        self.url = None
        self.position_seconds = 0
        self.duration_seconds = 0
        self.volume = 100
        self.is_paused = True
        self.is_muted = False
        self.search_results = []
        self.last_command_at = None

    def format_position(self) -> str:
        """Return 'current / total' as human-readable time string."""
        return f"{_fmt_time(self.position_seconds)} / {_fmt_time(self.duration_seconds)}"

    def update_from_js(self, js_state: dict) -> None:
        """
        Update state from JS video element snapshot.
        Вызывается из auto-save loop каждые 30 секунд.
        """
        self.position_seconds = int(js_state.get("current_time", self.position_seconds))
        self.duration_seconds = int(js_state.get("duration", self.duration_seconds))
        self.volume = int(js_state.get("volume", self.volume))
        self.is_paused = bool(js_state.get("paused", self.is_paused))
        self.is_muted = bool(js_state.get("muted", self.is_muted))
        self.last_command_at = datetime.now()


def _fmt_time(total_seconds: int) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    if total_seconds <= 0:
        return "0:00"
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
