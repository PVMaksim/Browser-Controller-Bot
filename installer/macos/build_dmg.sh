#!/bin/bash
# installer/macos/build_dmg.sh
# Сборка macOS .dmg дистрибутива
# Требования: create-dmg (brew install create-dmg), PyInstaller
# Использование: bash installer/macos/build_dmg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_NAME="SecureBrowserBot"
DMG_NAME="${APP_NAME}.dmg"
VERSION=$(grep 'APP_VERSION' "$ROOT_DIR/src/config/constants.py" | grep -oP '"\K[^"]+' | head -1)

echo "═══════════════════════════════════════════════"
echo "  Secure Browser Bot — macOS Build"
echo "  Version: $VERSION"
echo "═══════════════════════════════════════════════"
echo ""

# ── Шаг 1: PyInstaller ────────────────────────────────────────────
echo "📦 [1/4] Сборка .app через PyInstaller..."
cd "$ROOT_DIR"
pyinstaller installer/macos/SecureBrowserBot.spec \
    --clean \
    --noconfirm \
    --log-level WARN

APP_PATH="$DIST_DIR/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "❌ .app не найден в $DIST_DIR"
    exit 1
fi
echo "✅ .app собран: $APP_PATH"

# ── Шаг 2: Проверяем наличие create-dmg ───────────────────────────
echo ""
echo "🔍 [2/4] Проверка зависимостей..."
if ! command -v create-dmg &> /dev/null; then
    echo "❌ create-dmg не найден. Установи: brew install create-dmg"
    exit 1
fi
echo "✅ create-dmg: $(create-dmg --version 2>&1 | head -1)"

# ── Шаг 3: Сборка DMG ─────────────────────────────────────────────
echo ""
echo "💿 [3/4] Создание .dmg..."
DMG_STAGING="$DIST_DIR/dmg_staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"

create-dmg \
    --volname "$APP_NAME $VERSION" \
    --volicon "$SCRIPT_DIR/icon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "${APP_NAME}.app" 150 185 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 450 185 \
    --no-internet-enable \
    "$DIST_DIR/${DMG_NAME}" \
    "$APP_PATH"

echo "✅ DMG создан: $DIST_DIR/${DMG_NAME}"

# ── Шаг 4: Итог ───────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Сборка завершена успешно"
echo ""
SIZE=$(du -sh "$DIST_DIR/${DMG_NAME}" | cut -f1)
echo "  📦 $DMG_NAME ($SIZE)"
echo "  📍 $DIST_DIR/${DMG_NAME}"
echo "═══════════════════════════════════════════════"
