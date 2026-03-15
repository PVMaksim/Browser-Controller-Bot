# src/platform/cli.py
"""
Command-line interface for service management.
Устанавливает и управляет ботом как системным сервисом (launchd / NSSM).

Использование:
  python -m src.service_platform.cli install    # Установить как сервис автозапуска
  python -m src.service_platform.cli uninstall  # Удалить сервис
  python -m src.service_platform.cli start      # Запустить сервис
  python -m src.service_platform.cli stop       # Остановить сервис
  python -m src.service_platform.cli status     # Показать статус

macOS:  управляет launchd plist в ~/Library/LaunchAgents/
Windows: управляет NSSM-сервисом (требует права администратора для install/uninstall)
"""

import argparse
import sys

from loguru import logger


def _get_manager():
    """Return platform-appropriate service manager."""
    from src.service_platform.service_manager import get_service_manager
    return get_service_manager()


def cmd_install(args: argparse.Namespace) -> int:
    """Install bot as a system autostart service."""
    try:
        mgr = _get_manager()
        mgr.install()
        print("✅ Сервис установлен.")
        print("   Бот будет запускаться автоматически при входе в систему.")
        print("   Запустить сейчас: python -m src.service_platform.cli start")
        return 0
    except PermissionError:
        print("❌ Недостаточно прав. Запусти с правами администратора.")
        return 1
    except Exception as e:
        print(f"❌ Ошибка установки: {e}")
        logger.exception("Service install failed")
        return 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove service (stop if running, then uninstall)."""
    try:
        mgr = _get_manager()
        mgr.uninstall()
        print("✅ Сервис удалён.")
        return 0
    except PermissionError:
        print("❌ Недостаточно прав. Запусти с правами администратора.")
        return 1
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
        logger.exception("Service uninstall failed")
        return 1


def cmd_start(args: argparse.Namespace) -> int:
    """Start the service."""
    try:
        _get_manager().start()
        print("✅ Сервис запущен.")
        return 0
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        return 1


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the service."""
    try:
        _get_manager().stop()
        print("✅ Сервис остановлен.")
        return 0
    except Exception as e:
        print(f"❌ Ошибка остановки: {e}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show service status."""
    try:
        status = _get_manager().status()
        print(f"📊 Статус сервиса: {status}")
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1


_COMMANDS = {
    "install":   (cmd_install,   "Установить как сервис автозапуска"),
    "uninstall": (cmd_uninstall, "Удалить сервис"),
    "start":     (cmd_start,     "Запустить сервис"),
    "stop":      (cmd_stop,      "Остановить сервис"),
    "status":    (cmd_status,    "Показать статус сервиса"),
}


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m src.service_platform.cli",
        description="Secure Browser Bot — управление системным сервисом",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {cmd:<12} {desc}" for cmd, (_, desc) in _COMMANDS.items()
        ),
    )
    parser.add_argument(
        "command",
        choices=list(_COMMANDS.keys()),
        help="Команда управления сервисом",
    )
    return parser


def main() -> int:
    """Entry point for CLI."""
    parser = build_parser()
    args = parser.parse_args()
    fn, _ = _COMMANDS[args.command]
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
