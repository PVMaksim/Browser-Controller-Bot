# src/platform/menu_bar.py
"""
macOS menu bar icon via rumps library.
Показывает иконку в системном трее с меню управления ботом.
Запускается в отдельном потоке — не блокирует asyncio event loop бота.

Требования: pip install rumps  (добавлено в requirements.txt)
Работает только на macOS — на Windows используется systray через pystray.
"""

import platform
import threading
from typing import Callable

from loguru import logger


def start_menu_bar(
    on_quit: Callable[[], None],
    on_status: Callable[[], str],
) -> None:
    """
    Start menu bar icon in a background thread.
    Вызывается из main() после инициализации бота.

    on_quit: callable без аргументов — вызывается при выборе «Остановить бот»
    on_status: callable без аргументов → str — возвращает статус для отображения
    """
    if platform.system() != "Darwin":
        logger.debug("Menu bar: skipped (not macOS)")
        return

    try:
        import rumps
    except ImportError:
        logger.warning("rumps not installed — menu bar icon disabled. Run: pip install rumps")
        return

    class SecureBotApp(rumps.App):
        def __init__(self) -> None:
            super().__init__(
                name="SecureBrowserBot",
                title="🤖",  # Иконка в menu bar (можно заменить на .icns файл)
                menu=[
                    rumps.MenuItem("Статус", callback=self.show_status),
                    None,  # Разделитель
                    rumps.MenuItem("Открыть Telegram", callback=self.open_telegram),
                    None,
                    rumps.MenuItem("Остановить бот", callback=self.quit_app),
                ],
                quit_button=None,  # Убираем стандартную кнопку Quit
            )

        @rumps.clicked("Статус")
        def show_status(self, _) -> None:
            status = on_status()
            rumps.alert(title="Secure Browser Bot", message=status)

        @rumps.clicked("Открыть Telegram")
        def open_telegram(self, _) -> None:
            import subprocess
            subprocess.run(["open", "https://t.me/"], check=False)

        @rumps.clicked("Остановить бот")
        def quit_app(self, _) -> None:
            rumps.alert(
                title="Остановить бот?",
                message="Бот будет остановлен. Launchd перезапустит его при следующем входе в систему.",
                ok="Остановить",
            )
            on_quit()
            rumps.quit_application()

    def _run() -> None:
        try:
            SecureBotApp().run()
        except Exception as e:
            logger.error(f"Menu bar error: {e}")

    # Запускаем в daemon-потоке — не мешает завершению процесса
    thread = threading.Thread(target=_run, name="menu_bar", daemon=True)
    thread.start()
    logger.info("Menu bar icon started")


def show_notification(title: str, message: str, subtitle: str = "") -> None:
    """
    Show macOS system notification.
    Используется при первом запуске для onboarding-инструкции.
    Работает без rumps через osascript.
    """
    if platform.system() != "Darwin":
        return
    import subprocess

    script = (
        f'display notification "{message}" '
        f'with title "{title}"'
        + (f' subtitle "{subtitle}"' if subtitle else "")
    )
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception as e:
        logger.debug(f"Notification failed: {e}")
