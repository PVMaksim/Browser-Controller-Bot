# Distribution Guide — Сборка и публикация

## Обзор

Secure Browser Bot собирается в нативные дистрибутивы:
- **macOS**: `.app` + `.dmg` (PyInstaller + create-dmg)
- **Windows**: `.exe` установщик (PyInstaller + Inno Setup)

Сборка происходит автоматически в GitHub Actions при создании Git-тега.

---

## Автоматическая сборка (рекомендуется)

### 1. Обнови версию

В `src/config/constants.py`:
```python
APP_VERSION = "1.1.0"  # bump here before tagging
```

### 2. Закоммить и создать тег

```bash
git add src/config/constants.py
git commit -m "chore: bump version to 1.1.0"
git tag v1.1.0
git push origin main --tags
```

### 3. GitHub Actions запустится автоматически

Workflow `.github/workflows/build.yml` запустится и:
- Соберёт macOS `.dmg` на `macos-latest`
- Соберёт Windows `.exe` на `windows-latest`
- Создаст GitHub Release с обоими файлами

Посмотреть статус сборки: вкладка `Actions` в репозитории.

---

## Ручная сборка

### macOS .dmg

**Требования:**
```bash
brew install ffmpeg create-dmg
pip install pyinstaller
playwright install chromium
```

**Сборка:**
```bash
bash scripts/build_dist.sh
# Результат: dist/SecureBrowserBot.dmg
```

### Windows .exe

**Требования:**
- Python 3.11+
- ffmpeg (через winget или вручную)
- Inno Setup 6 (https://jrsoftware.org/isinfo.php)
- PyInstaller

**Сборка:**
```powershell
# Зависимости
pip install -r requirements.txt
pip install pyinstaller
playwright install chromium

# .exe бинарник
pyinstaller installer\windows\SecureBrowserBot.spec --clean --noconfirm

# Установщик (запускать после установки Inno Setup)
iscc installer\windows\installer.iss
# Результат: dist\SecureBrowserBot-Setup-1.1.0.exe
```

---

## Структура дистрибутива

### macOS .app
```
SecureBrowserBot.app/
└── Contents/
    ├── Info.plist          # Метаданные: bundle ID, версия, разрешения
    ├── MacOS/
    │   └── SecureBrowserBot   # Исполняемый файл
    └── Resources/
        └── icon.icns       # Иконка
```

`LSUIElement = true` — приложение работает только в menu bar,
иконка НЕ отображается в Dock.

### Windows .exe
Одиночный исполняемый файл со всеми зависимостями внутри.
Устанавливается в `%ProgramFiles%\SecureBrowserBot\`.

---

## Что включено в дистрибутив

| Компонент | Включён | Примечание |
|---|---|---|
| Python runtime | ✅ | Не нужен отдельно |
| aiogram | ✅ | |
| Playwright + Chromium | ✅ | Браузер скачивается при первом запуске |
| faster-whisper | ✅ | Модель скачивается при первом голосовом сообщении |
| ffmpeg | ❌ | Устанавливается через setup-скрипт |
| .env / config.json | ❌ | Пользователь создаёт сам при onboarding |

---

## Подписание кода (для публичного релиза)

### macOS
Для распространения вне App Store нужен Developer ID certificate:
```bash
codesign --force --deep --sign "Developer ID Application: ..." \
    dist/SecureBrowserBot.app
```
Без подписи macOS Gatekeeper покажет предупреждение — пользователь
должен нажать "Открыть" в System Preferences → Security.

### Windows
Подписание через `signtool` (требует Code Signing Certificate):
```cmd
signtool sign /fd SHA256 /t http://timestamp.digicert.com \
    dist\SecureBrowserBot.exe
```

---

## Changelog — как обновить пользователей

Бот не имеет автообновлений (это сделано намеренно — безопасность).
Для обновления пользователь:
1. Скачивает новый `.dmg` / `.exe` с GitHub Releases
2. Устанавливает поверх старого
3. Данные (`config.json`, `watch_history.json`, `watchlist.json`) сохраняются в системной папке и не затрагиваются при обновлении
