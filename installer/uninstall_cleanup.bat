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
REM PG data lives in ProgramData (versioned), NOT under the install dir.
if "%PROGRAMDATA%"=="" set "PROGRAMDATA=C:\ProgramData"
set "PG_DATA=%PROGRAMDATA%\NeuroX\pgdata17"

if exist "%PG_CTL%" (
    echo Stopping PostgreSQL...
    "%PG_CTL%" stop -D "%PG_DATA%" -m fast > nul 2>&1
    REM Give it a moment to shut down.
    REM IMPORTANT: do NOT use `timeout` here — this bat runs with Inno Setup's
    REM `runhidden` flag (no console attached), and `timeout.exe` will abort
    REM with "Input redirection is not supported" and KILL the calling cmd.exe
    REM process. Use `ping` instead, which works fine under runhidden.
    ping -n 3 127.0.0.1 > nul

    REM Force kill if still running
    "%PG_CTL%" status -D "%PG_DATA%" > nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Force-stopping PostgreSQL...
        "%PG_CTL%" stop -D "%PG_DATA%" -m immediate > nul 2>&1
    )
    REM Belt-and-braces: clean up postmaster.pid in case shutdown didn't.
    if exist "%PG_DATA%\postmaster.pid" del /f /q "%PG_DATA%\postmaster.pid" > nul 2>&1
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
