; ===========================================================================
; NeuroX Offline Installer - Inno Setup Script
; ===========================================================================
; Packages the complete NeuroX application for offline Windows installation:
;   - Electron frontend (win-unpacked)
;   - Python backend with all dependencies (wheels + embeddable Python)
;   - PaddleOCR AI models (pre-downloaded)
;   - PostgreSQL portable database server
;
; Build prerequisites:
;   1. Run  .\installer\download_deps.ps1  to populate installer\bundle\
;   2. Compile this .iss with Inno Setup 6.x
;
; The installer:
;   - Lets the user choose the installation directory
;   - Runs post-install setup (pip install from wheels, DB init)
;   - Creates desktop & Start Menu shortcuts
;   - Generates a full uninstaller
;   - Logs every step to {app}\logs\inno_install.log
; ===========================================================================

#define MyAppName      "NeuroX"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "NeuroX Team"
#define MyAppExeName   "ElectronReactApp.exe"
#define BundleDir      "..\installer\bundle"

[Setup]
AppId={{B8F3A2D1-7C4E-4F8A-9D2B-5E6F1A3C8D9E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Allow the user to choose the install location
DisableDirPage=no
; Allow the user to choose Start Menu group
DisableProgramGroupPage=no
OutputDir=..\installer\output
OutputBaseFilename=NeuroX-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
; Require admin for PostgreSQL service registration
PrivilegesRequired=admin
; Setup logging - written to the install directory
SetupLogging=yes
; Minimum Windows 10
MinVersion=10.0
; Uninstall info
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\frontend\{#MyAppExeName}
; Architecture
ArchitecturesAllowed=x64compatible
; Show installation progress in detail
ShowLanguageDialog=auto
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french";  MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Frontend (Electron app)
Source: "{#BundleDir}\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs

; Python embeddable
Source: "{#BundleDir}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; Pip wheels (offline cache)
Source: "{#BundleDir}\wheels\*"; DestDir: "{app}\wheels"; Flags: ignoreversion recursesubdirs createallsubdirs

; PaddleOCR models
Source: "{#BundleDir}\models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs

; PostgreSQL portable
Source: "{#BundleDir}\pgsql\*"; DestDir: "{app}\pgsql"; Flags: ignoreversion recursesubdirs createallsubdirs

; Backend source code
Source: "{#BundleDir}\backend_src\*"; DestDir: "{app}\backend_src"; Flags: ignoreversion recursesubdirs createallsubdirs

; Installer scripts
Source: "..\installer\setup_neurox.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\installer\uninstall_cleanup.bat"; DestDir: "{app}"; Flags: ignoreversion

; Create logs directory
[Dirs]
Name: "{app}\logs"; Permissions: users-full

[Icons]
; Desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\frontend\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\frontend\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startmenuicon
; Start Menu uninstall shortcut
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Post-install setup: install pip packages, create database, generate launcher
Filename: "{cmd}"; Parameters: "/c ""{app}\setup_neurox.bat"" ""{app}"""; \
    StatusMsg: "Setting up Python environment and database..."; \
    Flags: runhidden waituntilterminated; \
    Description: "Configure NeuroX components"

; Optionally launch the app after install
Filename: "{app}\frontend\{#MyAppExeName}"; \
    Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent; \
    WorkingDir: "{app}"

[UninstallRun]
; Run cleanup before uninstall removes files
Filename: "{cmd}"; Parameters: "/c ""{app}\uninstall_cleanup.bat"" ""{app}"""; \
    Flags: runhidden waituntilterminated

[UninstallDelete]
; Clean up generated files not tracked by installer
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\pgsql\data\log"
Type: filesandordirs; Name: "{app}\python\Lib"
Type: filesandordirs; Name: "{app}\python\Scripts"
Type: filesandordirs; Name: "{app}\backend_src\__pycache__"
Type: filesandordirs; Name: "{app}\backend_src\api\__pycache__"

[Code]
// --- Pascal Script: Installation logging & validation ---------------------
var
  InstallLog: string;

procedure LogInstall(Msg: string);
begin
  InstallLog := InstallLog + GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':') + ' | ' + Msg + #13#10;
  Log(Msg);
end;

function InitializeSetup(): Boolean;
begin
  LogInstall('NeuroX Installer starting');
  LogInstall('OS: ' + GetWindowsVersionString);
  LogInstall('Installer version: {#MyAppVersion}');
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  LogPath: string;
begin
  case CurStep of
    ssInstall:
      LogInstall('Installation step: copying files to ' + ExpandConstant('{app}'));
    ssPostInstall:
      begin
        LogInstall('Post-install step: running setup scripts');
        // Write accumulated log to file
        LogPath := ExpandConstant('{app}\logs\inno_install.log');
        LogInstall('Installation log written to: ' + LogPath);
        SaveStringToFile(LogPath, InstallLog, False);
      end;
    ssDone:
      begin
        LogInstall('Installation completed successfully');
        LogPath := ExpandConstant('{app}\logs\inno_install.log');
        SaveStringToFile(LogPath, InstallLog, True);
      end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  case CurUninstallStep of
    usUninstall:
      Log('Starting NeuroX uninstallation');
    usPostUninstall:
      Log('NeuroX uninstallation complete');
  end;
end;

// Prevent installation if not enough disk space (need ~2 GB)
function NextButtonClick(CurPageID: Integer): Boolean;
var
  FreeMB, TotalMB: Cardinal;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    GetSpaceOnDisk(ExpandConstant('{app}'), True, FreeMB, TotalMB);
    if FreeMB < 2048 then  // 2 GB in megabytes
    begin
      MsgBox('Insufficient disk space. NeuroX requires at least 2 GB of free space.', mbError, MB_OK);
      Result := False;
    end;
    LogInstall('Selected install directory: ' + ExpandConstant('{app}'));
    LogInstall('Free disk space: ' + IntToStr(FreeMB) + ' MB');
  end;
end;
