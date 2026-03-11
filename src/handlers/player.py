# src/handlers/player.py
"""
Media player handlers: /find, inline keyboard callbacks, /watchlist.
Этап 4.5: поиск видео, управление воспроизведением, история, watchlist.
"""

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger

from src.config.settings import Settings
from src.middlewares.access_control import check_access
from src.player.controller import PlayerController
from src.player.keyboards import (
    build_player_keyboard,
    build_resume_keyboard,
    build_search_results_keyboard,
)
from src.player.state import _fmt_time
from src.player.watch_history import get_recent_history
from src.player.watchlist import (
    add_to_watchlist,
    clear_watchlist,
    get_watchlist,
    remove_from_watchlist,
)

# Платформы которые принимаем в /find
_PLATFORM_ALIASES: dict[str, str] = {
    "рутуб": "rutube", "рутубе": "rutube", "rutube": "rutube",
    "ютуб":  "youtube", "ютубе": "youtube", "youtube": "youtube",
    "вк":    "vk",   "vk": "vk",
    "ок":    "ok",   "одноклассники": "ok", "ok": "ok",
}
_PLATFORM_NAMES: dict[str, str] = {
    "rutube": "RuTube", "youtube": "YouTube", "vk": "VK Видео", "ok": "Одноклассники",
}


def get_player_router(settings: Settings, bot: Bot, player: PlayerController) -> Router:
    """Build and return player router with all media handlers."""
    r = Router()

    async def _guard(message: Message) -> bool:
        if not message.from_user:
            return False
        return await check_access(message.from_user.id, bot, settings)

    async def _guard_cb(cb: CallbackQuery) -> bool:
        if not cb.from_user:
            return False
        return await check_access(cb.from_user.id, bot, settings)

    # ------------------------------------------------------------------ #
    # /find — search                                                       #
    # ------------------------------------------------------------------ #

    @r.message(Command("find"))
    async def cmd_find(message: Message) -> None:
        """Handle /find [platform] <query>: search video on platform."""
        if not await _guard(message):
            await message.answer("⛔ Доступ запрещён.")
            return

        text = message.text or ""
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "❌ Укажи запрос.\n"
                "Пример: <code>/find Интерстеллар</code>\n"
                "Или: <code>/find рутуб Интерстеллар</code>"
            )
            return

        raw_arg = parts[1].strip()
        platform, query = _parse_find_arg(raw_arg)

        if not query:
            await message.answer("❌ Укажи название фильма или запрос.")
            return

        platform_name = _PLATFORM_NAMES.get(platform, platform)
        status = await message.answer(f"🔍 Ищу <i>{query}</i> на {platform_name}...")

        try:
            results = await player.search(query=query, platform=platform)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await status.edit_text(f"❌ Ошибка поиска: <code>{str(e)[:200]}</code>")
            return

        if not results:
            await status.edit_text(
                f"😔 <b>{platform_name}</b> — по запросу «{query}» ничего не найдено.\n"
                "Попробуй другой запрос или другую платформу."
            )
            return

        keyboard = build_search_results_keyboard(results)
        await status.edit_text(
            f"🔍 <b>{platform_name}</b> — «{query}» — найдено {len(results)}:\n\n"
            "Выбери видео:",
            reply_markup=keyboard,
        )

    # ------------------------------------------------------------------ #
    # Callback: open video by index                                        #
    # ------------------------------------------------------------------ #

    @r.callback_query(F.data.startswith("player:open:"))
    async def cb_open_video(callback: CallbackQuery) -> None:
        """Handle button press on search result: open video."""
        if not await _guard_cb(callback):
            await callback.answer("⛔ Доступ запрещён.")
            return

        index = int(callback.data.split(":")[2])  # type: ignore[union-attr]

        await callback.answer("▶️ Открываю...")
        try:
            info = await player.open_video(index)
        except Exception as e:
            await callback.message.edit_text(  # type: ignore[union-attr]
                f"❌ Не удалось открыть видео: <code>{str(e)[:200]}</code>"
            )
            return

        title = info["title"]
        platform = info["platform"]
        saved = info.get("saved")
        platform_name = _PLATFORM_NAMES.get(platform, platform)

        if saved and saved["position_sec"] > 60:
            # Предлагаем продолжить просмотр
            pos_str = _fmt_time(saved["position_sec"])
            await callback.message.edit_text(  # type: ignore[union-attr]
                f"▶️ Найдено в истории: <b>{title}</b>\n"
                f"Платформа: {platform_name}\n"
                f"Остановился на: <b>{pos_str}</b> / {_fmt_time(saved['duration_sec'])}",
                reply_markup=build_resume_keyboard(pos_str),
            )
        else:
            await callback.message.edit_text(  # type: ignore[union-attr]
                _player_header(title, platform_name),
                reply_markup=build_player_keyboard(platform),
            )

    # ------------------------------------------------------------------ #
    # Callback: resume / restart                                           #
    # ------------------------------------------------------------------ #

    @r.callback_query(F.data == "player:resume")
    async def cb_resume(callback: CallbackQuery) -> None:
        """Resume from saved position."""
        if not await _guard_cb(callback):
            return
        await callback.answer("⏩ Продолжаю...")
        try:
            saved = get_recent_history(limit=1)
            if saved and player.state.url:
                from src.player.watch_history import get_position
                pos = get_position(player.state.url)
                if pos:
                    await player.seek(0)  # сначала сброс
                    page = await player._get_page()
                    await player._get_platform(player.state.platform).seek_absolute(
                        page, pos["position_sec"]
                    )
                    await player.play()
        except Exception as e:
            logger.error(f"Resume failed: {e}")
        platform_name = _PLATFORM_NAMES.get(player.state.platform or "", "")
        await callback.message.edit_text(  # type: ignore[union-attr]
            _player_header(player.state.title or "—", platform_name),
            reply_markup=build_player_keyboard(player.state.platform or ""),
        )

    @r.callback_query(F.data == "player:restart")
    async def cb_restart(callback: CallbackQuery) -> None:
        """Restart video from beginning."""
        if not await _guard_cb(callback):
            return
        await callback.answer("🔄 Начинаю сначала...")
        try:
            page = await player._get_page()
            await player._get_platform(player.state.platform).seek_absolute(page, 0)
            await player.play()
        except Exception as e:
            logger.error(f"Restart failed: {e}")
        platform_name = _PLATFORM_NAMES.get(player.state.platform or "", "")
        await callback.message.edit_text(  # type: ignore[union-attr]
            _player_header(player.state.title or "—", platform_name),
            reply_markup=build_player_keyboard(player.state.platform or ""),
        )

    # ------------------------------------------------------------------ #
    # Callback: player controls                                            #
    # ------------------------------------------------------------------ #

    @r.callback_query(F.data == "player:play")
    async def cb_play(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        try:
            await player.play()
            await callback.answer("▶️")
        except Exception as e:
            await callback.answer(f"❌ {str(e)[:60]}", show_alert=True)

    @r.callback_query(F.data == "player:pause")
    async def cb_pause(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        try:
            await player.pause()
            await callback.answer("⏸")
        except Exception as e:
            await callback.answer(f"❌ {str(e)[:60]}", show_alert=True)

    @r.callback_query(F.data.startswith("player:seek:"))
    async def cb_seek(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        delta = int(callback.data.split(":")[2])  # type: ignore[union-attr]
        try:
            await player.seek(delta)
            sign = "+" if delta > 0 else ""
            await callback.answer(f"⏩ {sign}{delta}с")
        except Exception as e:
            await callback.answer(f"❌ {str(e)[:60]}", show_alert=True)

    @r.callback_query(F.data.startswith("player:vol:"))
    async def cb_volume(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        delta_str = callback.data.split(":")[2]  # type: ignore[union-attr]
        try:
            new_vol = await player.set_volume(delta_str)
            await callback.answer(f"🔊 {new_vol}%")
        except Exception as e:
            await callback.answer(f"❌ {str(e)[:60]}", show_alert=True)

    @r.callback_query(F.data == "player:mute")
    async def cb_mute(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        try:
            muted = await player.toggle_mute()
            await callback.answer("🔇 Тишина" if muted else "🔊 Звук включён")
        except Exception as e:
            await callback.answer(f"❌ {str(e)[:60]}", show_alert=True)

    @r.callback_query(F.data == "player:status")
    async def cb_status(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        state = await player.get_current_state()
        platform_name = _PLATFORM_NAMES.get(state.platform or "", state.platform or "—")
        status_text = (
            f"📊 <b>Статус плеера</b>\n\n"
            f"📺 Платформа: {platform_name}\n"
            f"🎬 Видео: {state.title or '—'}\n"
            f"⏱ Позиция: {state.format_position()}\n"
            f"🔊 Громкость: {state.volume}%"
            + (" 🔇" if state.is_muted else "")
            + ("\n⏸ Пауза" if state.is_paused else "\n▶️ Играет")
        )
        await callback.answer()
        await callback.message.answer(status_text)  # type: ignore[union-attr]

    @r.callback_query(F.data == "player:close")
    async def cb_close(callback: CallbackQuery) -> None:
        if not await _guard_cb(callback):
            return
        await callback.answer("⛔ Закрываю...")
        await player.close()
        await callback.message.edit_text("⛔ Плеер закрыт.")  # type: ignore[union-attr]

    # ------------------------------------------------------------------ #
    # /mediastat                                                           #
    # ------------------------------------------------------------------ #

    @r.message(Command("mediastat"))
    async def cmd_mediastat(message: Message) -> None:
        """Show current player state as text command."""
        if not await _guard(message):
            return
        state = await player.get_current_state()
        if not state.is_active:
            await message.answer("ℹ️ Плеер не активен. Используй /find для поиска.")
            return
        platform_name = _PLATFORM_NAMES.get(state.platform or "", state.platform or "—")
        await message.answer(
            f"📊 <b>Медиапульт</b>\n\n"
            f"📺 {platform_name}\n"
            f"🎬 {state.title or '—'}\n"
            f"⏱ {state.format_position()}\n"
            f"🔊 {state.volume}%" + (" 🔇" if state.is_muted else "")
            + ("\n⏸ Пауза" if state.is_paused else "\n▶️ Играет"),
            reply_markup=build_player_keyboard(state.platform or ""),
        )

    # ------------------------------------------------------------------ #
    # /watchlist                                                           #
    # ------------------------------------------------------------------ #

    @r.message(Command("watchlist"))
    async def cmd_watchlist(message: Message) -> None:
        """Show watch-later list with controls."""
        if not await _guard(message):
            return

        items = get_watchlist()
        if not items:
            await message.answer(
                "📋 Список «Посмотреть позже» пуст.\n\n"
                "Добавить: <code>/wladd &lt;url&gt;</code>"
            )
            return

        text_lines = [f"📋 <b>Посмотреть позже</b> — {len(items)} видео:\n"]
        for i, item in enumerate(items[:10], 1):
            platform_name = _PLATFORM_NAMES.get(item["platform"], item["platform"])
            dur = f" · {item['duration']}" if item.get("duration") else ""
            text_lines.append(f"{i}. {item['title'][:50]}{dur} — {platform_name}")

        await message.answer("\n".join(text_lines))

    @r.message(Command("wladd"))
    async def cmd_wladd(message: Message) -> None:
        """Add current or specified URL to watchlist."""
        if not await _guard(message):
            return

        text = message.text or ""
        parts = text.split(maxsplit=1)
        url = parts[1].strip() if len(parts) > 1 else player.state.url

        if not url:
            await message.answer("❌ Укажи URL или сначала открой видео через /find.")
            return

        title = player.state.title or url
        platform = player.state.platform or "rutube"
        duration = None

        added = add_to_watchlist(url=url, title=title, platform=platform, duration=duration)
        if added:
            await message.answer(f"✅ «{title[:60]}» добавлен в список «Посмотреть позже».")
        else:
            await message.answer("ℹ️ Это видео уже в списке.")

    @r.message(Command("wlclear"))
    async def cmd_wlclear(message: Message) -> None:
        """Clear entire watchlist."""
        if not await _guard(message):
            return
        count = clear_watchlist()
        await message.answer(f"🗑 Список очищен. Удалено {count} видео.")

    return r


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_find_arg(raw: str) -> tuple[str, str]:
    """
    Parse '/find [platform] query' argument.
    Returns (platform_key, query). Platform defaults to "rutube".
    """
    parts = raw.split(maxsplit=1)
    if len(parts) == 1:
        return "rutube", parts[0].strip()
    first = parts[0].lower()
    if first in _PLATFORM_ALIASES:
        return _PLATFORM_ALIASES[first], parts[1].strip()
    return "rutube", raw.strip()


def _player_header(title: str, platform_name: str) -> str:
    """Build player status header text."""
    return (
        f"▶️ <b>{title[:80]}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📺  {platform_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
