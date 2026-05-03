@echo off
REM ============================================================================
REM NeuroX Post-Installation Setup
REM Called by the Inno Setup installer after files are copied.
REM Installs Python packages from bundled wheels and creates the database.
REM ============================================================================
setlocal enabledelayedexpansion

set "INSTALL_DIR=%~1"
if "%INSTALL_DIR%"=="" set "INSTALL_DIR=%~dp0"

set "LOG_DIR=%INSTALL_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\install_setup.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

call :log "============================================"
call :log "NeuroX Post-Install Setup"
call :log "Install dir: %INSTALL_DIR%"
call :log "Date: %DATE% %TIME%"
call :log "============================================"

REM ── 1. Install Python packages from wheels ──────────────────────────────────
set "PYTHON=%INSTALL_DIR%\python\python.exe"
set "PIP=%INSTALL_DIR%\python\Scripts\pip.exe"
set "WHEELS=%INSTALL_DIR%\wheels"
set "REQUIREMENTS=%INSTALL_DIR%\backend_src\requirements.txt"

if not exist "%PYTHON%" (
    call :log "ERROR: Python not found at %PYTHON%"
    goto :pg_setup
)

call :log "Installing Python packages from offline wheel cache..."
"%PYTHON%" -m pip install --no-index --find-links="%WHEELS%" -r "%REQUIREMENTS%" --no-warn-script-location >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    call :log "WARNING: Some packages may not have installed correctly (exit code %ERRORLEVEL%)"
    call :log "Retrying with --no-deps for critical packages..."
    for %%p in (fastapi uvicorn rapidocr-onnxruntime onnxruntime loguru sqlalchemy asyncpg) do (
        "%PYTHON%" -m pip install --no-index --find-links="%WHEELS%" %%p --no-warn-script-location >> "%LOG_FILE%" 2>&1
    )
) else (
    call :log "Python packages installed successfully"
)

REM ── 2. OCR models ──────────────────────────────────────────────────────────────
REM RapidOCR ships its default PP-OCR ONNX models inside the wheel, so no
REM separate model directory is required. If %INSTALL_DIR%\models\ocr exists
REM with det.onnx / rec.onnx / cls.onnx files, the backend will use those
REM instead (via the NEUROX_MODELS_DIR env var set in the launcher).
set "MODELS_SRC=%INSTALL_DIR%\models\ocr"
if exist "%MODELS_SRC%" (
    call :log "Custom OCR models directory present: %MODELS_SRC%"
) else (
    call :log "No custom OCR models — using RapidOCR bundled defaults"
)

:pg_setup
call :log "Reached :pg_setup label"
REM ── 3. Initialize PostgreSQL database ───────────────────────────────────────
set "PG_BIN=%INSTALL_DIR%\pgsql\bin"
REM Versioned data dir: prevents clashes with legacy PG data from previous installs.
set "PG_EXPECTED_VERSION=17"
if "%PROGRAMDATA%"=="" set "PROGRAMDATA=C:\ProgramData"
set "PG_DATA=%PROGRAMDATA%\NeuroX\pgdata%PG_EXPECTED_VERSION%"
set "PG_LEGACY_DATA=%PROGRAMDATA%\NeuroX\pgdata"
set "PGPASSWORD=postgres"

if not exist "%PROGRAMDATA%\NeuroX" mkdir "%PROGRAMDATA%\NeuroX" >> "%LOG_FILE%" 2>&1
call :log "PostgreSQL expected major version: %PG_EXPECTED_VERSION%"
call :log "PostgreSQL data directory: %PG_DATA%"

if not exist "%PG_BIN%\pg_ctl.exe" (
    call :log "PostgreSQL binaries not found — skipping database setup"
    goto :create_db
)

REM Handle any legacy (unversioned) data dir from older NeuroX installs
if exist "%PG_LEGACY_DATA%\PG_VERSION" (
    set /p PG_LEGACY_VER=<"%PG_LEGACY_DATA%\PG_VERSION"
    call :log "Found legacy data dir '%PG_LEGACY_DATA%' version !PG_LEGACY_VER!"
    "%PG_BIN%\pg_ctl.exe" stop -D "%PG_LEGACY_DATA%" -m immediate >> "%LOG_FILE%" 2>&1
    set "PG_LEGACY_BACKUP=%PROGRAMDATA%\NeuroX\pgdata_legacy_backup_%RANDOM%"
    call :log "Moving legacy data to: !PG_LEGACY_BACKUP!"
    move "%PG_LEGACY_DATA%" "!PG_LEGACY_BACKUP!" >> "%LOG_FILE%" 2>&1
    if !ERRORLEVEL! neq 0 (
        call :log "WARNING: move failed, deleting legacy dir instead"
        rmdir /s /q "%PG_LEGACY_DATA%" >> "%LOG_FILE%" 2>&1
    )
)

REM Check if expected data dir exists and has compatible version
if exist "%PG_DATA%\PG_VERSION" (
    set /p PG_DATA_VERSION=<"%PG_DATA%\PG_VERSION"
    call :log "Existing data dir version: !PG_DATA_VERSION!"
    if not "!PG_DATA_VERSION!"=="%PG_EXPECTED_VERSION%" (
        call :log "Version !PG_DATA_VERSION! is incompatible with server %PG_EXPECTED_VERSION%"
        "%PG_BIN%\pg_ctl.exe" stop -D "%PG_DATA%" -m immediate >> "%LOG_FILE%" 2>&1
        set "PG_INCOMPAT_BACKUP=%PROGRAMDATA%\NeuroX\pgdata!PG_DATA_VERSION!_backup_%RANDOM%"
        call :log "Moving incompatible data to: !PG_INCOMPAT_BACKUP!"
        move "%PG_DATA%" "!PG_INCOMPAT_BACKUP!" >> "%LOG_FILE%" 2>&1
        if !ERRORLEVEL! neq 0 (
            call :log "WARNING: move failed, deleting incompatible dir instead"
            rmdir /s /q "%PG_DATA%" >> "%LOG_FILE%" 2>&1
        )
        call :log "Initializing fresh PostgreSQL data directory..."
        "%PG_BIN%\initdb.exe" -D "%PG_DATA%" -U postgres -E UTF8 --locale=C >> "%LOG_FILE%" 2>&1
        if !ERRORLEVEL! neq 0 (
            call :log "ERROR: PostgreSQL re-initialization failed"
            goto :finish
        )
        call :log "PostgreSQL re-initialized on version %PG_EXPECTED_VERSION%"
    ) else (
        call :log "PostgreSQL data directory already initialized and compatible"
    )
) else (
    call :log "Initializing PostgreSQL data directory..."
    "%PG_BIN%\initdb.exe" -D "%PG_DATA%" -U postgres -E UTF8 --locale=C >> "%LOG_FILE%" 2>&1
    if %ERRORLEVEL% neq 0 (
        call :log "ERROR: PostgreSQL initialization failed"
        goto :finish
    )
    call :log "PostgreSQL initialized"
)

REM Fix data directory permissions so Electron app (non-admin) can access it
call :log "Fixing data directory permissions..."
REM Grant BUILTIN\Users (SID S-1-5-32-545) full control, locale-independent
icacls "%PROGRAMDATA%\NeuroX" /grant *S-1-5-32-545:(OI)(CI)F /T /C >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    call :log "WARNING: Failed to update PostgreSQL data ACLs"
) else (
    call :log "PostgreSQL data ACLs updated"
)

REM ── Force PostgreSQL to listen on a non-conflicting port ─────────────────
REM On Windows machines with Hyper-V / WSL2 / Docker / Windows Sandbox
REM enabled, port 5432 frequently lands inside Hyper-V's dynamically-reserved
REM port range ("netsh int ipv4 show excludedportrange"), causing PG to fail
REM at bind() with "Permission denied" - exactly what we saw in v1.0.4 logs.
REM Use 55432 which is well outside the typical reserved ranges. We also
REM force listen_addresses to localhost to avoid surprises with IPv6.
set "NEUROX_PG_PORT=55432"
set "PG_CONF=%PG_DATA%\postgresql.conf"

REM Make sure no PG is currently running against this data dir before we
REM touch its config (a leftover postmaster from a previous install would
REM still be on the old port). pg_ctl stop is idempotent — failure is fine.
"%PG_BIN%\pg_ctl.exe" stop -D "%PG_DATA%" -m immediate >> "%LOG_FILE%" 2>&1
if exist "%PG_DATA%\postmaster.pid" del /f /q "%PG_DATA%\postmaster.pid" >> "%LOG_FILE%" 2>&1

if exist "%PG_CONF%" (
    call :log "Patching postgresql.conf to use port %NEUROX_PG_PORT%..."
    REM Append (overrides any earlier port= since later wins in postgresql.conf)
    >>"%PG_CONF%" echo.
    >>"%PG_CONF%" echo # NeuroX: forced port to avoid Hyper-V reserved range conflicts
    >>"%PG_CONF%" echo port = %NEUROX_PG_PORT%
    >>"%PG_CONF%" echo listen_addresses = 'localhost'
    call :log "postgresql.conf patched"
) else (
    call :log "WARNING: postgresql.conf not found at %PG_CONF%"
)

REM Start PostgreSQL temporarily to create the database.
REM
REM IMPORTANT: do NOT redirect pg_ctl's stdout/stderr to %LOG_FILE%. On
REM Windows, the spawned postmaster INHERITS the parent cmd's redirected
REM standard handles. If we point them at %LOG_FILE%, postmaster keeps that
REM file handle open for its entire lifetime, which prevents subsequent
REM `>>` appends in this script from working (cmd silently stops logging
REM and the rest of setup never runs). v1.0.5 hit this exact bug as soon as
REM PG actually managed to start. Redirect to a dedicated file instead, so
REM postmaster's inherited handle is on a file we don't need to write again.
call :log "Starting PostgreSQL for database creation..."
"%PG_BIN%\pg_ctl.exe" start -D "%PG_DATA%" -w -l "%LOG_DIR%\postgresql_setup.log" > "%LOG_DIR%\pg_ctl_start.txt" 2>&1
call :log "pg_ctl start returned !ERRORLEVEL!"

REM NOTE: do NOT use `timeout` here. Inno Setup runs this bat with the
REM `runhidden` flag, which means there is no console attached. Under those
REM conditions `timeout.exe` aborts with "Input redirection is not supported"
REM and KILLS the entire calling cmd.exe process — this caused v1.0.2 and
REM v1.0.3 to silently exit right after `pg_ctl start` and never run any of
REM the database-creation logic below. `pg_ctl -w` already blocks until the
REM server is ready, so no extra wait is needed. If a wait is ever required
REM here, use `ping -n 4 127.0.0.1 >nul` instead — it works under runhidden.

:create_db
call :log "Reached :create_db label"
REM Create the neurox database. Using psql with `CREATE DATABASE` is more
REM reliable than createdb.exe on locked-down Windows machines.
REM
REM IMPORTANT: this section is intentionally NOT wrapped in `if exist (...)`
REM parens — CMD's pre-parser silently aborts complex blocks containing
REM `for /f` + escaped redirection + nested quotes (this caused v1.0.2 to
REM emit zero log lines after pg_ctl start). Use goto for flow control.
if not exist "%PG_BIN%\psql.exe" goto :finish

call :log "Attempting to create 'neurox' database..."
"%PG_BIN%\psql.exe" -U postgres -h localhost -p %NEUROX_PG_PORT% -d postgres -c "CREATE DATABASE neurox;" >> "%LOG_FILE%" 2>&1
set "CREATE_RC=!ERRORLEVEL!"
if !CREATE_RC! equ 0 (
    call :log "Database 'neurox' created successfully"
) else (
    call :log "CREATE DATABASE returned !CREATE_RC! - DB may already exist, will verify with SELECT"
)

REM Verify the database is reachable. If this fails, the DB really doesn't
REM exist and we cannot continue with table init / user seeding.
"%PG_BIN%\psql.exe" -U postgres -h localhost -p %NEUROX_PG_PORT% -d neurox -c "SELECT 1" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! neq 0 (
    call :log "ERROR: Cannot connect to 'neurox' DB - skipping init_db.py"
    goto :stop_pg
)
call :log "Verified 'neurox' DB is reachable"

REM Run database initialization (create tables + seed default user)
if not exist "%PYTHON%" goto :stop_pg
call :log "Running init_db.py (tables + default admin user)..."
set "DATABASE_URL=postgresql://postgres@localhost:%NEUROX_PG_PORT%/neurox"
"%PYTHON%" "%INSTALL_DIR%\backend_src\init_db.py" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! equ 0 (
    call :log "Database initialized (tables + default admin user 'admin')"
) else (
    call :log "WARNING: init_db.py exited with code !ERRORLEVEL!"
)

:stop_pg
REM Stop PostgreSQL (it will be started by the app launcher)
call :log "Stopping PostgreSQL..."
"%PG_BIN%\pg_ctl.exe" stop -D "%PG_DATA%" -m fast >> "%LOG_FILE%" 2>&1
REM Belt-and-braces: clean up postmaster.pid in case shutdown didn't
if exist "%PG_DATA%\postmaster.pid" (
    call :log "Removing leftover postmaster.pid"
    del /f /q "%PG_DATA%\postmaster.pid" >> "%LOG_FILE%" 2>&1
)

:finish
call :log "Reached :finish label"
REM ── 4. Create a launcher script ────────────────────────────────────────────
set "LAUNCHER=%INSTALL_DIR%\NeuroX.bat"
(
    echo @echo off
    echo setlocal
    echo set "INSTALL_DIR=%%~dp0"
    echo set "NEUROX_MODELS_DIR=%%INSTALL_DIR%%models\ocr"
    echo set "NEUROX_LOG_DIR=%%INSTALL_DIR%%logs"
    echo set "DATABASE_URL=postgresql://postgres@localhost:55432/neurox"
    echo set "NEUROX_PG_DATA=%%PROGRAMDATA%%\NeuroX\pgdata17"
    echo.
    echo REM Clean up any stale postmaster.pid from a crash or unclean shutdown.
    echo if exist "%%NEUROX_PG_DATA%%\postmaster.pid" ^(
    echo     "%%INSTALL_DIR%%pgsql\bin\pg_ctl.exe" status -D "%%NEUROX_PG_DATA%%" ^>nul 2^>^&1
    echo     if errorlevel 3 del /f /q "%%NEUROX_PG_DATA%%\postmaster.pid"
    echo ^)
    echo.
    echo REM Start PostgreSQL
    echo if exist "%%INSTALL_DIR%%pgsql\bin\pg_ctl.exe" ^(
    echo     "%%INSTALL_DIR%%pgsql\bin\pg_ctl.exe" start -D "%%NEUROX_PG_DATA%%" -w -l "%%INSTALL_DIR%%logs\postgresql.log"
    echo ^)
    echo.
    echo REM Start the application
    echo start "" "%%INSTALL_DIR%%frontend\ElectronReactApp.exe"
) > "%LAUNCHER%"
call :log "Launcher script created at %LAUNCHER%"

call :log "============================================"
call :log "Post-install setup complete"
call :log "============================================"

exit /b 0

:log
echo %DATE% %TIME% ^| %~1 >> "%LOG_FILE%"
echo %~1
goto :eof
