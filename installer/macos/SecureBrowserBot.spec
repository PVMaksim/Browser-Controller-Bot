# installer/macos/SecureBrowserBot.spec
# PyInstaller spec для сборки macOS .app
# Использование:
#   pyinstaller installer/macos/SecureBrowserBot.spec
# или через скрипт:
#   bash scripts/build_dist.sh

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent.parent  # корень проекта

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules
aiogram_hiddenimports = collect_submodules('aiogram')


import sys as _sys, sysconfig as _sc, os as _os
_stdlib = _sc.get_path('stdlib')
_plat_py = _os.path.join(_stdlib, 'platform.py')
if not _os.path.exists(_plat_py):
    _plat_py = _os.path.join(_os.path.dirname(_os.__file__), 'platform.py')

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Включаем шаблон конфига
        (str(ROOT / ".env.example"), "."),
        # Иконка приложения
        (str(ROOT / "installer" / "macos" / "icon.icns"), "."),
        # Real stdlib platform.py — fixes PyInstaller frozen stub bug
        (_plat_py, '.'),
        # sitecustomize.py runs before all user code and patches aiogram Router
        (str(ROOT / 'installer' / 'macos' / 'sitecustomize.py'), '.'),
    ],
    hiddenimports=[
        # aiogram traced automatically by PyInstaller
        *aiogram_hiddenimports,
        # Playwright
        "playwright",
        "playwright.async_api",
        # faster-whisper
        "faster_whisper",
        # platformdirs, loguru, dotenv
        "platformdirs",
        "loguru",
        "dotenv",
        "psutil",
        # rumps (опционально)
        "rumps",
        # Все платформенные модули
        "src.platform.launchd",
        "src.platform.menu_bar",
        "src.player.platforms.rutube",
        "src.player.platforms.youtube",
        "src.player.platforms.vk_video",
        "src.player.platforms.ok_video",
        "src.system.macos_commands",
        "src.system.dispatcher",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / 'installer' / 'macos' / 'rthook_aaa_platform.py')],
    excludes=[
        # Исключаем тяжёлые неиспользуемые пакеты
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "pkg_resources",
        "setuptools",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SecureBrowserBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Нет терминального окна
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "installer" / "macos" / "icon.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SecureBrowserBot",
)

# Создаём .app bundle
app = BUNDLE(
    coll,
    name="SecureBrowserBot.app",
    icon=str(ROOT / "installer" / "macos" / "icon.icns"),
    bundle_identifier="com.securebrowserbot.app",
    info_plist={
        "CFBundleDisplayName": "Secure Browser Bot",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        # Разрешаем запуск от имени агента (без Dock-иконки)
        "LSUIElement": True,
        # Разрешения для управления браузером
        "NSAppleEventsUsageDescription": "Приложению нужен доступ к System Events для управления компьютером.",
        "NSSystemAdministrationUsageDescription": "Используется для системных команд (сон, блокировка экрана).",
    },
)
