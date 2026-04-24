@echo off
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

set "PYTHON=%INSTALL_DIR%\python\python.exe"
set "WHEELS=%INSTALL_DIR%\wheels"
set "REQUIREMENTS=%INSTALL_DIR%\backend_src\requirements.txt"

if not exist "%PYTHON%" (
    call :log "ERROR: Python not found"
    goto :pg_setup
)

call :log "Installing Python packages from offline wheel cache..."
"%PYTHON%" -m pip install --no-index --find-links="%WHEELS%" -r "%REQUIREMENTS%" --no-warn-script-location >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    call :log "WARNING: Some packages may not have installed correctly (exit code %ERRORLEVEL%)"
    call :log "Retrying critical packages..."
    for %%p in (fastapi uvicorn paddleocr paddlepaddle loguru sqlalchemy asyncpg) do (
        "%PYTHON%" -m pip install --no-index --find-links="%WHEELS%" %%p --no-warn-script-location >> "%LOG_FILE%" 2>&1
    )
) else (
    call :log "Python packages installed successfully"
)

if exist "%INSTALL_DIR%\models" call :log "PaddleOCR models directory found"

:pg_setup
set "PG_BIN=%INSTALL_DIR%\pgsql\bin"
set "PGPORT=5433"
set "PGDATA=%PROGRAMDATA%\NeuroX\pgdata"
set "PGPASSWORD=postgres"

if not exist "%PROGRAMDATA%\NeuroX" mkdir "%PROGRAMDATA%\NeuroX" >> "%LOG_FILE%" 2>&1
call :log "PostgreSQL data directory: %PGDATA%"
call :log "PostgreSQL port: %PGPORT%"

if not exist "%PG_BIN%\pg_ctl.exe" (
    call :log "PostgreSQL binaries not found ? skipping database setup"
    goto :create_launcher
)

if exist "%PGDATA%\PG_VERSION" (
    call :log "PostgreSQL data directory already initialized"
) else (
    call :log "Initializing PostgreSQL data directory..."
    "%PG_BIN%\initdb.exe" -D "%PGDATA%" -U postgres -E UTF8 --locale=C -p %PGPORT% >> "%LOG_FILE%" 2>&1
    if %ERRORLEVEL% neq 0 (
        call :log "ERROR: PostgreSQL initialization failed"
        goto :create_launcher
    )
    call :log "PostgreSQL initialized"
)

call :log "Fixing data directory permissions..."
icacls "%PROGRAMDATA%\NeuroX" /grant *S-1-5-32-545:(OI)(CI)F /T /C >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    call :log "WARNING: Failed to update PostgreSQL data ACLs"
) else (
    call :log "PostgreSQL data ACLs updated"
)

call :log "Starting PostgreSQL on port %PGPORT%..."
"%PG_BIN%\pg_ctl.exe" start -D "%PGDATA%" -p %PGPORT% -w -l "%LOG_DIR%\postgresql_setup.log" >> "%LOG_FILE%" 2>&1
timeout /t 3 /nobreak > nul

if exist "%PG_BIN%\psql.exe" (
    call :log "Creating neurox database..."
    "%PG_BIN%\psql.exe" -U postgres -p %PGPORT% -tc "SELECT 1 FROM pg_database WHERE datname = 'neurox'" | findstr "1" > nul 2>&1
    if %ERRORLEVEL% neq 0 (
        "%PG_BIN%\createdb.exe" -U postgres -p %PGPORT% neurox >> "%LOG_FILE%" 2>&1
        if %ERRORLEVEL% equ 0 call :log "Database 'neurox' created successfully"
    ) else (
        call :log "Database 'neurox' already exists"
    )

    if exist "%PYTHON%" (
        call :log "Running database table initialization..."
        pushd "%INSTALL_DIR%\backend_src"
        set "DATABASE_URL=postgresql://postgres@localhost:%PGPORT%/neurox"
        "%PYTHON%" init_db.py >> "%LOG_FILE%" 2>&1
        popd
        call :log "Database tables initialized"
    )
)

call :log "Stopping PostgreSQL (will be restarted by launcher)..."
"%PG_BIN%\pg_ctl.exe" stop -D "%PGDATA%" -p %PGPORT% -m fast >> "%LOG_FILE%" 2>&1

:create_launcher
set "LAUNCHER=%INSTALL_DIR%\NeuroX.bat"
(
    echo @echo off
    echo setlocal
    echo set "INSTALL_DIR=%%~dp0"
    echo set "PADDLEX_HOME=%%INSTALL_DIR%%models"
    echo set "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True"
    echo set "NEUROX_LOG_DIR=%%INSTALL_DIR%%logs"
    echo set "DATABASE_URL=postgresql://postgres@localhost:5433/neurox"
    echo set "NEUROX_PG_DATA=%%PROGRAMDATA%%\NeuroX\pgdata"
    echo.
    echo if exist "%%INSTALL_DIR%%pgsql\bin\pg_ctl.exe" ^(
    echo     "%%INSTALL_DIR%%pgsql\bin\pg_ctl.exe" start -D "%%NEUROX_PG_DATA%%" -p 5433 -w -l "%%INSTALL_DIR%%logs\postgresql.log"
    echo ^)
    echo.
    echo start "NeuroX Backend" /b "%%INSTALL_DIR%%python\python.exe" "%%INSTALL_DIR%%backend_src\api\main_paddleocr.py"
    echo.
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
