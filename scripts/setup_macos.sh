#!/bin/bash
# scripts/setup_macos.sh
# Первичная настройка macOS для Secure Browser Bot
set -euo pipefail

echo "═══════════════════════════════════════════════════"
echo "  Secure Browser Bot — Setup for macOS             "
echo "═══════════════════════════════════════════════════"

# Проверяем что запущено на macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ Этот скрипт только для macOS"
    exit 1
fi

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
echo "📁 Директория проекта: $PROJECT_DIR"

echo ""
echo "🔧 [1/6] Проверка Xcode Command Line Tools..."
if ! xcode-select -p &>/dev/null; then
    echo "⚠️  Xcode CLI Tools не найдены — устанавливаю..."
    xcode-select --install
    echo ""
    echo "   Дождись окончания установки Xcode CLI Tools,"
    echo "   затем перезапусти скрипт: bash scripts/setup_macos.sh"
    exit 0
fi
echo "✅ Xcode CLI Tools: $(xcode-select -p)"

echo ""
echo "📦 [2/6] Установка системных зависимостей..."
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew не найден. Установи: https://brew.sh"
    exit 1
fi
brew install ffmpeg python@3.11

echo ""
echo "🐍 [3/6] Установка Python-зависимостей..."
python3 scripts/install_deps.py
playwright install chromium
echo "✅ Зависимости установлены"

echo ""
echo "⚙️  [4/7] Проверка инструментов..."
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg не найден после установки"
    exit 1
fi
echo "✅ ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

if ! python3 -c "import playwright" 2>/dev/null; then
    echo "❌ playwright не установлен"
    exit 1
fi
echo "✅ playwright: $(python3 -c 'import playwright; print(playwright.__version__)')"

echo ""
echo "🔒 [5/7] Настройка прав доступа..."
mkdir -p tmp logs
if [ -f ".env" ]; then
    chmod 600 .env
    echo "✅ .env: права 600 установлены"
else
    cp .env.example .env
    echo "⚠️  .env создан из шаблона."
    echo "   ОБЯЗАТЕЛЬНО заполни BOT_TOKEN и ALLOWED_USER_ID перед запуском!"
fi

echo ""
echo "☕ [6/7] Запрет спящего режима при питании от сети..."
sudo pmset -c sleep 0
sudo pmset -c disksleep 0
echo "✅ Спящий режим отключён при питании от сети"

echo ""
echo "🚀 [7/7] Настройка автозапуска через launchd..."
PLIST_SRC="$PROJECT_DIR/com.user.secure-browser-bot.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.user.secure-browser-bot.plist"

if [ -f "$PLIST_SRC" ]; then
    # Подставляем реальный путь к Python и проекту в plist
    PYTHON_PATH="$(which python3)"
    sed -i '' "s|/usr/local/bin/python3|$PYTHON_PATH|g" "$PLIST_SRC"
    sed -i '' "s|/Users/username/secure-browser-bot|$PROJECT_DIR|g" "$PLIST_SRC"

    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$PLIST_SRC" "$PLIST_DST"
    launchctl load "$PLIST_DST"
    echo "✅ Сервис установлен и запущен"
else
    echo "⚠️  Файл plist не найден: $PLIST_SRC"
    echo "   Автозапуск не настроен. Запускай вручную: python3 src/main.py"
fi

echo ""
echo "🧪 Запуск тестов для проверки установки..."
if python3 -m pytest tests/unit/ -q --tb=short 2>/dev/null; then
    echo "✅ Все тесты прошли"
else
    echo "⚠️  Некоторые тесты не прошли — проверь конфигурацию"
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ Настройка завершена"
echo ""
echo "  Следующие шаги:"
echo "  1. Отредактируй .env (BOT_TOKEN + ALLOWED_USER_ID)"
echo "  2. Запусти: python3 src/main.py"
echo "  3. Отправь /start своему боту в Telegram"
echo "═══════════════════════════════════════════════════"
