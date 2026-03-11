#!/bin/bash
# scripts/health_check.sh
# Быстрая проверка состояния сервиса
set -euo pipefail

echo "═══════════════════════════════════════"
echo "  Secure Browser Bot — Health Check    "
echo "═══════════════════════════════════════"

PLIST_LABEL="com.user.secure-browser-bot"
LOG_DIR="$HOME/Library/Logs/SecureBrowserBot"

echo ""
echo "🔧 Сервис launchd:"
if launchctl list | grep -q "$PLIST_LABEL" 2>/dev/null; then
    echo "  ✅ Запущен ($PLIST_LABEL)"
else
    echo "  ❌ Не найден ($PLIST_LABEL)"
fi

echo ""
echo "🔧 Инструменты:"
if command -v python3 &>/dev/null; then
    echo "  ✅ python3: $(python3 --version)"
else
    echo "  ❌ python3 не найден"
fi

if command -v ffmpeg &>/dev/null; then
    echo "  ✅ ffmpeg: $(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f1-3)"
else
    echo "  ❌ ffmpeg не найден"
fi

echo ""
echo "📄 Последние 20 строк лога:"
LOG_FILE="$LOG_DIR/bot.log"
if [ -f "$LOG_FILE" ]; then
    tail -20 "$LOG_FILE"
else
    echo "  Лог-файл не найден: $LOG_FILE"
fi

echo ""
echo "═══════════════════════════════════════"
