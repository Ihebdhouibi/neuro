<#
.SYNOPSIS
    Downloads all offline dependencies for the NeuroX installer.
.DESCRIPTION
    Fetches Python embeddable, pip wheels, PaddleOCR models, and PostgreSQL
    portable binaries so the final installer can work without internet.
.NOTES
    Run from the repo root: .\installer\download_deps.ps1
    Requires: an existing backend venv at Neuro_backend\venv
#>

param(
    [string]$OutputDir = "installer\bundle",
    [string]$PythonVersion = "3.11.9",
    [string]$PgVersion = "17.4-1"       # EDB portable binaries version
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot   = Split-Path $PSScriptRoot -Parent
$BundleDir  = Join-Path $RepoRoot $OutputDir
$LogFile    = Join-Path $BundleDir "download.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$ts | $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

# ── Create folder structure ──────────────────────────────────────────────────
foreach ($sub in @("python", "wheels", "models", "pgsql", "frontend", "backend_src", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $BundleDir $sub) | Out-Null
}
Log "Bundle directory: $BundleDir"

# ══════════════════════════════════════════════════════════════════════════════
# 1. PYTHON EMBEDDABLE
# ══════════════════════════════════════════════════════════════════════════════
$pythonDir = Join-Path $BundleDir "python"
$pythonZip = Join-Path $BundleDir "python-embed.zip"
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"

if (-not (Test-Path (Join-Path $pythonDir "python.exe"))) {
    Log "Downloading Python $PythonVersion embeddable..."
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip -UseBasicParsing
    Expand-Archive -Path $pythonZip -DestinationPath $pythonDir -Force
    Remove-Item $pythonZip -ErrorAction SilentlyContinue

    # Enable pip: uncomment 'import site' in python3XX._pth
    $pthFile = Get-ChildItem $pythonDir -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $content = Get-Content $pthFile.FullName
        $content = $content -replace "^#import site", "import site"
        Set-Content -Path $pthFile.FullName -Value $content
        Log "Enabled 'import site' in $($pthFile.Name)"
    }

    # Install pip via get-pip.py
    $getPip = Join-Path $pythonDir "get-pip.py"
    Log "Downloading get-pip.py..."
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
    Log "Installing pip into embedded Python..."
    & (Join-Path $pythonDir "python.exe") $getPip --no-warn-script-location 2>&1 | Out-Null
    Log "pip installed successfully"
} else {
    Log "Python embeddable already present — skipping"
}

# ══════════════════════════════════════════════════════════════════════════════
# 2. PIP WHEELS (offline cache)
# ══════════════════════════════════════════════════════════════════════════════
$wheelsDir    = Join-Path $BundleDir "wheels"
$requirements = Join-Path $RepoRoot "Neuro_backend" "requirements.txt"

Log "Downloading pip wheels for offline install..."
$venvPip = Join-Path $RepoRoot "Neuro_backend" "venv" "Scripts" "pip.exe"
if (Test-Path $venvPip) {
    # Use the existing venv pip which already has the resolved deps
    & $venvPip download -r $requirements -d $wheelsDir --platform win_amd64 --python-version 311 --only-binary=:all: 2>&1 | ForEach-Object { Log "  $_" }
    # Also grab any source-only packages
    & $venvPip download -r $requirements -d $wheelsDir 2>&1 | ForEach-Object { Log "  $_" }
} else {
    Log "WARNING: venv pip not found at $venvPip — using embedded Python pip"
    $embedPip = Join-Path $pythonDir "Scripts" "pip.exe"
    & $embedPip download -r $requirements -d $wheelsDir 2>&1 | ForEach-Object { Log "  $_" }
}
$wheelCount = (Get-ChildItem $wheelsDir -Filter "*.whl").Count + (Get-ChildItem $wheelsDir -Filter "*.tar.gz").Count
Log "Downloaded $wheelCount wheel/source packages"

# ══════════════════════════════════════════════════════════════════════════════
# 3. PADDLEOCR MODELS (pre-download so first run doesn't need internet)
# ══════════════════════════════════════════════════════════════════════════════
$modelsDir = Join-Path $BundleDir "models"
$venvPython = Join-Path $RepoRoot "Neuro_backend" "venv" "Scripts" "python.exe"

Log "Pre-downloading PaddleOCR models..."
$modelScript = @"
import os, sys
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
paddlex_home = r'$modelsDir'
os.environ['PADDLEX_HOME'] = paddlex_home

from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='fr', use_gpu=False, show_log=True)
# Run on a tiny dummy image to force model download
import numpy as np
dummy = np.zeros((100, 300, 3), dtype=np.uint8)
dummy[20:80, 20:280] = 255
try:
    result = ocr.ocr(dummy, cls=True)
    print(f'Model download complete. PADDLEX_HOME={paddlex_home}')
except Exception as e:
    print(f'OCR test run note: {e}')
    print('Models should still be cached.')
print('Done')
"@

$modelScriptPath = Join-Path $BundleDir "download_models.py"
Set-Content -Path $modelScriptPath -Value $modelScript -Encoding UTF8
if (Test-Path $venvPython) {
    $env:PADDLEX_HOME = $modelsDir
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
    & $venvPython $modelScriptPath 2>&1 | ForEach-Object { Log "  $_" }
} else {
    Log "WARNING: Cannot pre-download models — venv python not found"
}
Remove-Item $modelScriptPath -ErrorAction SilentlyContinue
$modelSize = (Get-ChildItem $modelsDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Log "Models directory size: $([math]::Round($modelSize, 1)) MB"

# ══════════════════════════════════════════════════════════════════════════════
# 4. POSTGRESQL PORTABLE
# ══════════════════════════════════════════════════════════════════════════════
$pgsqlDir = Join-Path $BundleDir "pgsql"
$pgZipUrl = "https://get.enterprisedb.com/postgresql/postgresql-$PgVersion-windows-x64-binaries.zip"
$pgZip    = Join-Path $BundleDir "pgsql-portable.zip"

if (-not (Test-Path (Join-Path $pgsqlDir "bin" "pg_ctl.exe"))) {
    Log "Downloading PostgreSQL $PgVersion portable binaries..."
    Invoke-WebRequest -Uri $pgZipUrl -OutFile $pgZip -UseBasicParsing
    Log "Extracting PostgreSQL..."
    Expand-Archive -Path $pgZip -DestinationPath $BundleDir -Force
    # The zip extracts to pgsql/ inside $BundleDir — which is our target
    Remove-Item $pgZip -ErrorAction SilentlyContinue

    # Initialize the database cluster
    $initdb = Join-Path $pgsqlDir "bin" "initdb.exe"
    $dataDir = Join-Path $pgsqlDir "data"
    if (Test-Path $initdb) {
        Log "Initializing PostgreSQL data directory..."
        & $initdb -D $dataDir -U postgres -E UTF8 --locale=C 2>&1 | ForEach-Object { Log "  $_" }

        # Configure pg_hba.conf for local trust auth (single-user desktop app)
        $hbaPath = Join-Path $dataDir "pg_hba.conf"
        @"
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
"@ | Set-Content -Path $hbaPath -Encoding UTF8

        # Configure postgresql.conf for desktop use
        $confPath = Join-Path $dataDir "postgresql.conf"
        Add-Content -Path $confPath -Value @"

# NeuroX desktop configuration
listen_addresses = '127.0.0.1'
port = 5432
max_connections = 20
shared_buffers = 128MB
work_mem = 4MB
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 10MB
"@
        Log "PostgreSQL initialized with local trust authentication"
    }
} else {
    Log "PostgreSQL portable already present — skipping"
}

# ══════════════════════════════════════════════════════════════════════════════
# 5. COPY BACKEND SOURCE
# ══════════════════════════════════════════════════════════════════════════════
$backendSrc = Join-Path $BundleDir "backend_src"
$srcDir = Join-Path $RepoRoot "Neuro_backend"
Log "Copying backend source code..."

$backendItems = @("api", "templates", "database.py", "fill_template.py", "ocr_filter.py",
    "ocr_to_schema.py", "openai_extraction.py", "prescription_generator.py",
    "preprocess_for_ocr.py", "practitioners.py", "requirements.txt", "sample_schema.json",
    "init_db.py", "init_medical_lists.py", "medical_lists_seed.sql")

foreach ($item in $backendItems) {
    $src = Join-Path $srcDir $item
    $dst = Join-Path $backendSrc $item
    if (Test-Path $src) {
        if ((Get-Item $src).PSIsContainer) {
            Copy-Item $src $dst -Recurse -Force
        } else {
            $dstParent = Split-Path $dst -Parent
            New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
            Copy-Item $src $dst -Force
        }
    }
}
Log "Backend source copied"

# ══════════════════════════════════════════════════════════════════════════════
# 6. BUILD ELECTRON FRONTEND
# ══════════════════════════════════════════════════════════════════════════════
$frontendDir = Join-Path $RepoRoot "Neuro_frontend"
$frontendDist = Join-Path $BundleDir "frontend"

Log "Building Electron frontend (win-unpacked)..."
Push-Location $frontendDir
try {
    npm run build:unpack 2>&1 | ForEach-Object { Log "  $_" }
    $unpackedDir = Join-Path $frontendDir "dist" "win-unpacked"
    if (Test-Path $unpackedDir) {
        Copy-Item "$unpackedDir\*" $frontendDist -Recurse -Force
        Log "Frontend built and copied to bundle"
    } else {
        Log "WARNING: win-unpacked not found — frontend build may have failed"
    }
} finally {
    Pop-Location
}

# ══════════════════════════════════════════════════════════════════════════════
# 7. CREATE .ENV TEMPLATE FOR PRODUCTION
# ══════════════════════════════════════════════════════════════════════════════
$envTemplate = Join-Path $backendSrc ".env"
@"
# NeuroX Production Configuration
# Paths are relative to installation directory

DATABASE_URL=postgresql://postgres@localhost:5432/neurox
CORS_ORIGINS=*
LOG_LEVEL=INFO

# Center configuration
CENTER_NAME=CDS OPHTALMOLOGIE NANTERRE LA BOULE
CENTER_ADDRESS=123 Avenue de la République, 92000 Nanterre
CENTER_TEL=01 47 00 00 00
CENTER_EMAIL=contact@cds-nanterre.fr
CENTER_FINESS=920036563
CENTER_CITY=Nanterre

# Document management paths
EDM_BASE_PATH=C:/temp/fse_ocr
GALAXIE_EDM=D:/Stimut/Documents_Patients
"@ | Set-Content -Path $envTemplate -Encoding UTF8
Log "Production .env template created"

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
$totalSize = (Get-ChildItem $BundleDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Log "═══════════════════════════════════════════════════════════════"
Log "Bundle complete: $([math]::Round($totalSize, 0)) MB total"
Log "  Python:     $(Join-Path $BundleDir 'python')"
Log "  Wheels:     $wheelCount packages"
Log "  Models:     $([math]::Round($modelSize, 1)) MB"
Log "  PostgreSQL: $(Join-Path $BundleDir 'pgsql')"
Log "  Frontend:   $(Join-Path $BundleDir 'frontend')"
Log "  Backend:    $(Join-Path $BundleDir 'backend_src')"
Log "═══════════════════════════════════════════════════════════════"
Log "Next: run the Inno Setup compiler on installer\NeuroX_Installer.iss"
