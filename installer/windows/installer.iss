; installer/windows/installer.iss
; Inno Setup 6.x — сборка .exe установщика для Windows
; Использование: iscc installer\windows\installer.iss
; Требования: Inno Setup 6, файл dist\SecureBrowserBot.exe

#define MyAppName "Secure Browser Bot"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "SecureBrowserBot"
#define MyAppURL "https://github.com/user/secure-browser-bot"
#define MyAppExeName "SecureBrowserBot.exe"
#define MyAppId "{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Установщик не требует прав администратора для установки в AppData
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
OutputDir=..\..\dist
OutputBaseFilename=SecureBrowserBot-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Автозапуск — предлагаем, но не принудительно
CloseApplications=yes
; Разрешаем x64 и x86
ArchitecturesAllowed=x64 x86
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "autostart"; Description: "Запускать автоматически при входе в систему (рекомендуется)"; GroupDescription: "Дополнительные задачи:"

[Files]
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\.env.example";         DestDir: "{app}"; Flags: ignoreversion
Source: "README_FIRST.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\..\scripts\install_deps.py";           DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; Автозапуск через реестр (если пользователь выбрал задачу autostart)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Установка ffmpeg через winget если не установлен
Filename: "winget.exe"; Parameters: "install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements"; Description: "Установить ffmpeg (необходим для голосовых команд)"; Flags: nowait postinstall skipifsilent runasoriginaluser

; Запуск бота после установки
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Остановить бот перед удалением
Filename: "powershell.exe"; Parameters: "-Command ""Stop-Process -Name SecureBrowserBot -Force -ErrorAction SilentlyContinue"""; Flags: runhidden

[Code]
// Проверяем наличие .NET / Visual C++ Redistributable при необходимости
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
