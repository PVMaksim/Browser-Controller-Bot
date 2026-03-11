#!/usr/bin/env python3
"""
scripts/install_deps.py
Умная установка зависимостей с fallback на бинарные колёса.

Проблема: pydantic-core, greenlet и ряд других пакетов требуют
компилятора C (Xcode CLI Tools на macOS, Visual C++ Build Tools на Windows).
Без него pip падает с «Failed building wheel».

Решение:
  1. Пробуем обычную установку requirements.txt
  2. Если упало на C-расширении — повторяем только сбойные пакеты
     с --only-binary=:all: (используем готовые wheel-файлы с PyPI)
  3. Если и это не помогло — выводим точную инструкцию по установке компилятора

Использование:
  python scripts/install_deps.py              # основные зависимости
  python scripts/install_deps.py --dev        # + dev-зависимости
  python scripts/install_deps.py --stealth    # + playwright-stealth
  python scripts/install_deps.py --ocr        # + easyocr
"""

import sys
import io
# Windows CI runners use CP1252 by default — force UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import subprocess
import sys
import re
from pathlib import Path

# Пакеты с C-расширениями — для них пробуем --only-binary в первую очередь
C_EXTENSION_PACKAGES = {
    "pydantic-core",
    "greenlet",
    "aiohttp",
    "multidict",
    "yarl",
    "frozenlist",
    "charset-normalizer",
    "cryptography",
    "cffi",
}

COMPILER_HELP = {
    "darwin": """
╔══════════════════════════════════════════════════════════════╗
║  Нужны Xcode Command Line Tools                              ║
║                                                              ║
║  Запусти:  xcode-select --install                            ║
║  Дождись установки, затем повтори:                           ║
║    python scripts/install_deps.py                            ║
╚══════════════════════════════════════════════════════════════╝
""",
    "win32": """
╔══════════════════════════════════════════════════════════════╗
║  Нужны Visual C++ Build Tools                                ║
║                                                              ║
║  1. Скачай: https://visualstudio.microsoft.com/              ║
║             visual-cpp-build-tools/                          ║
║  2. При установке выбери:                                    ║
║     "Desktop development with C++"                          ║
║  3. Перезапусти терминал и повтори:                          ║
║     python scripts\\install_deps.py                          ║
╚══════════════════════════════════════════════════════════════╝
""",
    "linux": """
╔══════════════════════════════════════════════════════════════╗
║  Нужны build-essential и заголовки Python                    ║
║                                                              ║
║  Ubuntu/Debian:                                              ║
║    sudo apt install python3-dev build-essential              ║
║                                                              ║
║  Затем повтори:                                              ║
║    python scripts/install_deps.py                            ║
╚══════════════════════════════════════════════════════════════╝
""",
}


def _pip(*args: str) -> tuple[int, str]:
    """Run pip with given args, return (returncode, combined output)."""
    cmd = [sys.executable, "-m", "pip", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def _extract_failed_packages(error_output: str) -> list[str]:
    """Parse pip error output to find which packages failed to build."""
    failed = []
    # Pattern: "Failed to build <pkg1> <pkg2>"
    for m in re.finditer(r"Failed to build ([\w\-]+)", error_output):
        failed.append(m.group(1))
    # Pattern: "Failed building wheel for <pkg>"
    for m in re.finditer(r"Failed building wheel for ([\w\-]+)", error_output):
        pkg = m.group(1)
        if pkg not in failed:
            failed.append(pkg)
    return failed


def install_requirements(req_file: Path, label: str = "") -> bool:
    """
    Install from a requirements file with smart fallback.
    Returns True on success.
    """
    tag = f"[{label}] " if label else ""
    print(f"\n{tag}📦 Устанавливаю {req_file.name}...")

    # ── Попытка 1: обычная установка ──────────────────────────────
    code, out = _pip("install", "-r", str(req_file), "--quiet")
    if code == 0:
        print(f"{tag}✅ Готово")
        return True

    print(f"{tag}⚠️  Обычная установка не удалась, анализирую ошибку...")

    # ── Попытка 2: C-расширения через --only-binary ────────────────
    failed_pkgs = _extract_failed_packages(out)
    c_ext_failed = [p for p in failed_pkgs if p.lower() in C_EXTENSION_PACKAGES]

    if c_ext_failed:
        print(f"{tag}🔧 Пробую бинарные колёса для: {', '.join(c_ext_failed)}")
        bin_args = ["install", "--only-binary=:all:"] + c_ext_failed + ["--quiet"]
        code2, out2 = _pip(*bin_args)
        if code2 == 0:
            # Повторяем полную установку — остальные пакеты
            print(f"{tag}🔄 Повторяю полную установку...")
            code3, out3 = _pip("install", "-r", str(req_file), "--quiet")
            if code3 == 0:
                print(f"{tag}✅ Готово (через бинарные колёса)")
                return True
            out = out3
        else:
            out = out2

    # ── Попытка 3: весь файл через --only-binary ───────────────────
    print(f"{tag}🔧 Пробую --only-binary=:all: для всего файла...")
    code4, out4 = _pip("install", "-r", str(req_file), "--only-binary=:all:", "--quiet")
    if code4 == 0:
        print(f"{tag}✅ Готово (все пакеты через бинарные колёса)")
        return True

    # ── Все попытки исчерпаны ──────────────────────────────────────
    print(f"\n{tag}❌ Установка не удалась\n")
    print("Вывод pip:")
    print(out[-2000:])  # последние 2000 символов

    platform = sys.platform
    if platform.startswith("linux"):
        platform = "linux"
    help_text = COMPILER_HELP.get(platform, COMPILER_HELP["linux"])
    print(help_text)
    return False


def main() -> None:
    root = Path(__file__).parent.parent
    args = sys.argv[1:]

    steps: list[tuple[Path, str]] = [(root / "requirements.txt", "main")]

    if "--dev" in args:
        steps.append((root / "requirements-dev.txt", "dev"))

    # Апгрейд pip сначала — старый pip часто не умеет в бинарные колёса
    print("🔄 Обновляю pip...")
    _pip("install", "--upgrade", "pip", "--quiet")

    ok = True
    for req_file, label in steps:
        if not req_file.exists():
            print(f"⚠️  Файл не найден: {req_file}")
            continue
        if not install_requirements(req_file, label):
            ok = False

    if "--stealth" in args:
        print("\n[stealth] 📦 Устанавливаю playwright-stealth...")
        code, _ = _pip("install", "playwright-stealth", "--quiet")
        if code == 0:
            print("[stealth] ✅ Готово")
        else:
            code2, _ = _pip("install", "playwright-stealth", "--only-binary=:all:", "--quiet")
            print("[stealth] ✅ Готово" if code2 == 0 else "[stealth] ⚠️  Не удалось установить")

    if "--ocr" in args:
        print("\n[ocr] 📦 Устанавливаю easyocr (~130 МБ моделей при первом запуске)...")
        code, _ = _pip("install", "easyocr", "--quiet")
        if code == 0:
            print("[ocr] ✅ Готово")
        else:
            code2, _ = _pip("install", "easyocr", "--only-binary=:all:", "--quiet")
            print("[ocr] ✅ Готово" if code2 == 0 else "[ocr] ⚠️  Не удалось установить")

    if ok:
        print("\n✅ Все зависимости установлены")
        print("   Следующий шаг: playwright install chromium")
    else:
        print("\n❌ Некоторые зависимости не установлены — следуй инструкции выше")
        sys.exit(1)


if __name__ == "__main__":
    main()
