# scripts/setup_windows.ps1
# Первичная настройка Windows для Secure Browser Bot
# Запуск: PowerShell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Secure Browser Bot — Setup for Windows   " -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── [1/5] Python ──────────────────────────────────────────────────
Write-Host "[1/5] Проверка Python..." -ForegroundColor Yellow
$pyVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Python не найден. Установи Python 3.11+ с python.org" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ $pyVersion" -ForegroundColor Green

# ── [2/5] ffmpeg via winget ───────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Установка ffmpeg..." -ForegroundColor Yellow
try {
    $ffmpegCheck = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "  ✅ ffmpeg уже установлен: $ffmpegCheck" -ForegroundColor Green
} catch {
    Write-Host "  ⬇️  Устанавливаю ffmpeg через winget..." -ForegroundColor Yellow
    winget install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
    # Обновляем PATH в текущей сессии
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-Host "  ✅ ffmpeg установлен" -ForegroundColor Green
}

# ── [3/5] nircmd (для управления громкостью) ─────────────────────
Write-Host ""
Write-Host "[3/5] Установка nircmd..." -ForegroundColor Yellow
$nircmdPath = "$env:LOCALAPPDATA\nircmd\nircmd.exe"
if (Test-Path $nircmdPath) {
    Write-Host "  ✅ nircmd уже установлен" -ForegroundColor Green
} else {
    $nircmdDir = "$env:LOCALAPPDATA\nircmd"
    New-Item -ItemType Directory -Force -Path $nircmdDir | Out-Null
    $downloadUrl = "https://www.nirsoft.net/utils/nircmd-x64.zip"
    $zipPath = "$env:TEMP\nircmd.zip"
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -TimeoutSec 30
        Expand-Archive -Path $zipPath -DestinationPath $nircmdDir -Force
        Remove-Item $zipPath
        # Добавляем в PATH пользователя
        $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
        if ($userPath -notlike "*nircmd*") {
            [System.Environment]::SetEnvironmentVariable("PATH", "$userPath;$nircmdDir", "User")
        }
        Write-Host "  ✅ nircmd установлен" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  nircmd не установлен — управление громкостью будет ограничено" -ForegroundColor Yellow
    }
}

# ── [3.5/5] Visual C++ Build Tools check ─────────────────────────
Write-Host ""
Write-Host "[3.5/5] Проверка Visual C++ Build Tools..." -ForegroundColor Yellow
$vcInstalled = $false
$vcPaths = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio",
    "${env:ProgramFiles}\Microsoft Visual Studio",
    "${env:ProgramFiles(x86)}\Microsoft Visual C++ Build Tools"
)
foreach ($p in $vcPaths) {
    if (Test-Path $p) { $vcInstalled = $true; break }
}
# Проверяем через cl.exe в PATH
if (-not $vcInstalled) {
    try { cl.exe 2>&1 | Out-Null; $vcInstalled = $true } catch {}
}

if (-not $vcInstalled) {
    Write-Host "  ⚠️  Visual C++ Build Tools не найдены." -ForegroundColor Yellow
    Write-Host "  Без них некоторые пакеты (pydantic-core, greenlet)" -ForegroundColor Yellow
    Write-Host "  будут установлены как бинарные колёса (это нормально)." -ForegroundColor Yellow
    Write-Host "  Для полной поддержки: https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Yellow
} else {
    Write-Host "  ✅ Visual C++ Build Tools найдены" -ForegroundColor Green
}

# ── [4/5] Python зависимости ──────────────────────────────────────
Write-Host ""
Write-Host "[4/5] Установка Python-зависимостей..." -ForegroundColor Yellow
# Используем умный установщик с fallback на бинарные колёса
python scripts\install_deps.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Установка зависимостей не удалась" -ForegroundColor Red
    Write-Host "  Установи Visual C++ Build Tools и повтори:" -ForegroundColor Yellow
    Write-Host "  https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Yellow
    exit 1
}
playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Host "  ❌ Ошибка playwright install" -ForegroundColor Red; exit 1 }
Write-Host "  ✅ Зависимости установлены" -ForegroundColor Green

# ── [5/5] .env ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Настройка конфига..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ⚠️  .env создан из шаблона. Заполни BOT_TOKEN и ALLOWED_USER_ID." -ForegroundColor Yellow
} else {
    Write-Host "  ✅ .env уже существует" -ForegroundColor Green
}

Write-Host ""
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ Настройка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "  Следующий шаг:" -ForegroundColor White
Write-Host "  1. Заполни .env (BOT_TOKEN и ALLOWED_USER_ID)" -ForegroundColor White
Write-Host "  2. Запусти: python src\main.py" -ForegroundColor White
Write-Host "  3. Или установи как сервис: python -m src.platform.cli install" -ForegroundColor White
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
