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
    for %%p in (fastapi uvicorn paddleocr paddlepaddle loguru sqlalchemy asyncpg) do (
        "%PYTHON%" -m pip install --no-index --find-links="%WHEELS%" %%p --no-warn-script-location >> "%LOG_FILE%" 2>&1
    )
) else (
    call :log "Python packages installed successfully"
)

REM ── 2. Copy PaddleOCR models to the right location ─────────────────────────
set "MODELS_SRC=%INSTALL_DIR%\models"
set "PADDLEX_HOME=%INSTALL_DIR%\models"

if exist "%MODELS_SRC%" (
    call :log "PaddleOCR models directory: %MODELS_SRC%"
    call :log "Models will be used from install directory (no download needed)"
) else (
    call :log "WARNING: Models directory not found — OCR will download models on first use"
)

:pg_setup
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

REM Start PostgreSQL temporarily to create the database
call :log "Starting PostgreSQL for database creation..."
"%PG_BIN%\pg_ctl.exe" start -D "%PG_DATA%" -w -l "%LOG_DIR%\postgresql_setup.log" >> "%LOG_FILE%" 2>&1

REM Wait a moment for PostgreSQL to be ready
timeout /t 3 /nobreak > nul

:create_db
REM Create the neurox database if it doesn't exist
if exist "%PG_BIN%\psql.exe" (
    call :log "Creating neurox database..."
    "%PG_BIN%\psql.exe" -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'neurox'" | findstr "1" > nul 2>&1
    if %ERRORLEVEL% neq 0 (
        "%PG_BIN%\createdb.exe" -U postgres neurox >> "%LOG_FILE%" 2>&1
        if %ERRORLEVEL% equ 0 (
            call :log "Database 'neurox' created successfully"
        ) else (
            call :log "WARNING: Could not create database (may already exist)"
        )
    ) else (
        call :log "Database 'neurox' already exists"
    )

    REM Run database initialization (create tables)
    if exist "%PYTHON%" (
        call :log "Running database table initialization..."
        set "DATABASE_URL=postgresql://postgres@localhost:5432/neurox"
        "%PYTHON%" "%INSTALL_DIR%\backend_src\init_db.py" >> "%LOG_FILE%" 2>&1
        call :log "Database tables initialized"
    )

    REM Stop PostgreSQL (it will be started by the app launcher)
    call :log "Stopping PostgreSQL..."
    "%PG_BIN%\pg_ctl.exe" stop -D "%PG_DATA%" -m fast >> "%LOG_FILE%" 2>&1
)

:finish
REM ── 4. Create a launcher script ────────────────────────────────────────────
set "LAUNCHER=%INSTALL_DIR%\NeuroX.bat"
(
    echo @echo off
    echo setlocal
    echo set "INSTALL_DIR=%%~dp0"
    echo set "PADDLEX_HOME=%%INSTALL_DIR%%models"
    echo set "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True"
    echo set "NEUROX_LOG_DIR=%%INSTALL_DIR%%logs"
    echo set "DATABASE_URL=postgresql://postgres@localhost:5432/neurox"
    echo set "NEUROX_PG_DATA=%%PROGRAMDATA%%\NeuroX\pgdata17"
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
