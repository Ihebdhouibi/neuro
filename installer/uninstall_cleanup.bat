@echo off
REM ============================================================================
REM NeuroX Uninstallation Cleanup
REM Stops services and cleans up runtime data before Inno Setup removes files.
REM ============================================================================
setlocal enabledelayedexpansion

set "INSTALL_DIR=%~1"
if "%INSTALL_DIR%"=="" set "INSTALL_DIR=%~dp0"

echo NeuroX Uninstall Cleanup
echo Install dir: %INSTALL_DIR%

REM ── 1. Kill the Electron app if running ─────────────────────────────────────
echo Stopping NeuroX application...
taskkill /f /im ElectronReactApp.exe > nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq *neurox*" > nul 2>&1

REM ── 2. Stop PostgreSQL ──────────────────────────────────────────────────────
set "PG_CTL=%INSTALL_DIR%\pgsql\bin\pg_ctl.exe"
set "PG_DATA=%INSTALL_DIR%\pgsql\data"

if exist "%PG_CTL%" (
    echo Stopping PostgreSQL...
    "%PG_CTL%" stop -D "%PG_DATA%" -m fast > nul 2>&1
    REM Give it a moment to shut down
    timeout /t 2 /nobreak > nul
    
    REM Force kill if still running
    "%PG_CTL%" status -D "%PG_DATA%" > nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Force-stopping PostgreSQL...
        "%PG_CTL%" stop -D "%PG_DATA%" -m immediate > nul 2>&1
    )
    echo PostgreSQL stopped
)

REM ── 3. Clean up runtime data ────────────────────────────────────────────────
echo Cleaning up runtime data...

REM Remove Python cache files
if exist "%INSTALL_DIR%\python" (
    for /r "%INSTALL_DIR%\python" %%f in (__pycache__) do (
        if exist "%%f" rd /s /q "%%f" > nul 2>&1
    )
)
if exist "%INSTALL_DIR%\backend_src" (
    for /r "%INSTALL_DIR%\backend_src" %%f in (__pycache__) do (
        if exist "%%f" rd /s /q "%%f" > nul 2>&1
    )
)

echo Cleanup complete
exit /b 0
