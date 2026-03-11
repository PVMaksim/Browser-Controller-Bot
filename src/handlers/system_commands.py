# src/handlers/system_commands.py
"""
System command handlers: /sleep, /lock, /vol_sys, /mute_sys, /sysinfo, /copy.
Этап 8: используем get_system_commands() — работает на macOS и Windows.
"""

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from src.config.settings import Settings
from src.middlewares.access_control import check_access


def get_system_router(settings: Settings, bot: Bot) -> Router:
    """Build system commands router (cross-platform)."""
    r = Router()

    async def _guard(message: Message) -> bool:
        if not message.from_user:
            return False
        return await check_access(message.from_user.id, bot, settings)

    def _get_arg(message: Message) -> str:
        text = message.text or ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    def _sys():
        """Lazy-load platform commands module."""
        from src.system.dispatcher import get_system_commands
        return get_system_commands()

    @r.message(Command("sleep"))
    async def cmd_sleep(message: Message) -> None:
        """Put computer to sleep."""
        if not await _guard(message):
            return
        try:
            await _sys().sleep_mac()
            await message.answer("😴 Компьютер уходит в сон...")
        except NotImplementedError as e:
            await message.answer(f"⚠️ {e}")
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{e}</code>")

    @r.message(Command("lock"))
    async def cmd_lock(message: Message) -> None:
        """Lock screen."""
        if not await _guard(message):
            return
        try:
            await _sys().lock_screen()
            await message.answer("🔒 Экран заблокирован.")
        except NotImplementedError as e:
            await message.answer(f"⚠️ {e}")
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{e}</code>")

    @r.message(Command("vol_sys"))
    async def cmd_vol_sys(message: Message) -> None:
        """Set system output volume 0–100."""
        if not await _guard(message):
            return
        raw = _get_arg(message)
        if not raw or not raw.isdigit():
            await message.answer(
                "❌ Укажи уровень 0–100.\nПример: <code>/vol_sys 50</code>"
            )
            return
        try:
            level = await _sys().set_system_volume(int(raw))
            await message.answer(f"🔊 Системная громкость: {level}%")
        except NotImplementedError as e:
            await message.answer(f"⚠️ {e}")
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{e}</code>")

    @r.message(Command("mute_sys"))
    async def cmd_mute_sys(message: Message) -> None:
        """Toggle system audio mute."""
        if not await _guard(message):
            return
        try:
            await _sys().toggle_system_mute()
            await message.answer("🔇 Системный звук переключён.")
        except NotImplementedError as e:
            await message.answer(f"⚠️ {e}")
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{e}</code>")

    @r.message(Command("sysinfo"))
    async def cmd_sysinfo(message: Message) -> None:
        """Show CPU, RAM, disk info."""
        if not await _guard(message):
            return
        try:
            info = await _sys().get_system_info()
            await message.answer(info.format_telegram())
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{e}</code>")

    @r.message(Command("copy"))
    async def cmd_copy(message: Message) -> None:
        """Copy text to clipboard."""
        if not await _guard(message):
            return
        text = _get_arg(message)
        if not text:
            await message.answer("❌ Укажи текст.\nПример: <code>/copy Hello</code>")
            return
        try:
            await _sys().copy_to_clipboard(text)
            await message.answer(f"📋 Скопировано: <code>{text[:100]}</code>")
        except NotImplementedError as e:
            await message.answer(f"⚠️ {e}")
        except Exception as e:
            await message.answer(f"❌ Ошибка: <code>{e}</code>")

    return r
