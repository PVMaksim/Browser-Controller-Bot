#!/bin/bash
# scripts/build_dist.sh
# Сборка macOS дистрибутива (.app + .dmg)
# На CI запускается автоматически при создании Git-тега.
# Локально: bash scripts/build_dist.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "═══════════════════════════════════════════"
echo "  Secure Browser Bot — Distribution Build"
echo "═══════════════════════════════════════════"

cd "$ROOT_DIR"

# Проверка зависимостей
echo ""
echo "🔍 Проверка инструментов..."
for tool in python3 pyinstaller create-dmg; do
    if ! command -v "$tool" &> /dev/null; then
        echo "❌ $tool не найден"
        [[ "$tool" == "create-dmg" ]] && echo "   Установи: brew install create-dmg"
        [[ "$tool" == "pyinstaller" ]] && echo "   Установи: pip install pyinstaller"
        exit 1
    fi
    echo "  ✅ $tool: $(command -v $tool)"
done

# Установка зависимостей
echo ""
echo "📦 Установка Python-зависимостей..."
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

# Очистка предыдущей сборки
echo ""
echo "🧹 Очистка dist/..."
rm -rf dist/ build/

# Сборка .app + .dmg
echo ""
echo "🔨 Запуск build_dmg.sh..."
bash installer/macos/build_dmg.sh

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Готово! Файлы в директории dist/"
ls -lh dist/*.dmg 2>/dev/null || true
echo "═══════════════════════════════════════════"
