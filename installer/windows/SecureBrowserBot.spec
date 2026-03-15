# installer/windows/SecureBrowserBot.spec
# PyInstaller spec для сборки Windows .exe
# Использование:
#   pyinstaller installer\\windows\\SecureBrowserBot.spec
# или через скрипт:
#   scripts\\build_dist_windows.ps1

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent.parent  # корень проекта

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / ".env.example"), "."),
        (str(ROOT / "installer" / "windows" / "icon.ico"), "."),
    ],
    hiddenimports=[
        "aiogram",
        "aiogram.client",
        "aiogram.types",
        "aiogram.filters",
        "playwright",
        "playwright.async_api",
        "faster_whisper",
        "platformdirs",
        "loguru",
        "dotenv",
        "psutil",
        # Windows-специфичные модули
        "src.service_platform.windows_service",
        "src.system.windows_commands",
        "src.system.dispatcher",
        # Платформенные модули плеера
        "src.player.platforms.rutube",
        "src.player.platforms.youtube",
        "src.player.platforms.vk_video",
        "src.player.platforms.ok_video",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas", "rumps"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SecureBrowserBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Нет консольного окна
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "installer" / "windows" / "icon.ico"),
    version=str(ROOT / "installer" / "windows" / "version_info.txt"),
)
