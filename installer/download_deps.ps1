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
    [string]$PgVersion = "17.4-1"
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

# --- Create folder structure ---
foreach ($sub in @("python", "wheels", "models", "pgsql", "libreoffice", "frontend", "backend_src", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $BundleDir $sub) | Out-Null
}
Log "Bundle directory: $BundleDir"

# ==========================================================================
# 1. PYTHON EMBEDDABLE
# ==========================================================================
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
    Log "Python embeddable already present -- skipping"
}

# ==========================================================================
# 2. PIP WHEELS (offline cache)
# ==========================================================================
$wheelsDir    = Join-Path $BundleDir "wheels"
$requirements = Join-Path (Join-Path $RepoRoot "Neuro_backend") "requirements.txt"

Log "Downloading pip wheels for offline install..."
$venvPip = Join-Path (Join-Path (Join-Path (Join-Path $RepoRoot "Neuro_backend") "venv") "Scripts") "pip.exe"
if (Test-Path $venvPip) {
    & $venvPip download -r $requirements -d $wheelsDir --platform win_amd64 --python-version 311 --only-binary=:all: 2>&1 | ForEach-Object { Log "  $_" }
    & $venvPip download -r $requirements -d $wheelsDir 2>&1 | ForEach-Object { Log "  $_" }
} else {
    Log "WARNING: venv pip not found at $venvPip -- using embedded Python pip"
    $embedPip = Join-Path (Join-Path $pythonDir "Scripts") "pip.exe"
    & $embedPip download -r $requirements -d $wheelsDir 2>&1 | ForEach-Object { Log "  $_" }
}
$wheelCount = @(Get-ChildItem $wheelsDir -Filter "*.whl" -ErrorAction SilentlyContinue).Count + @(Get-ChildItem $wheelsDir -Filter "*.tar.gz" -ErrorAction SilentlyContinue).Count
Log "Downloaded $wheelCount wheel/source packages"

# ==========================================================================
# 3. PADDLEOCR MODELS
# ==========================================================================
$modelsDir = Join-Path $BundleDir "models"
$venvPython = Join-Path (Join-Path (Join-Path (Join-Path $RepoRoot "Neuro_backend") "venv") "Scripts") "python.exe"

Log "Pre-downloading PaddleOCR models..."
$modelScriptPath = Join-Path $PSScriptRoot "download_models.py"
if ((Test-Path $venvPython) -and (Test-Path $modelScriptPath)) {
    $env:PADDLEX_HOME = $modelsDir
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
    $oldEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $venvPython $modelScriptPath 2>&1 | ForEach-Object { Log "  $_" }
    $ErrorActionPreference = $oldEAP

    # PaddleX may ignore PADDLEX_HOME and cache to default location
    $defaultCache = Join-Path (Join-Path $env:USERPROFILE ".paddlex") "official_models"
    if (Test-Path $defaultCache) {
        $modelNames = @("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec", "PP-LCNet_x1_0_textline_ori")
        New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
        $officialDir = Join-Path $modelsDir "official_models"
        New-Item -ItemType Directory -Force -Path $officialDir | Out-Null
        foreach ($mName in $modelNames) {
            $srcModel = Join-Path $defaultCache $mName
            $dstModel = Join-Path $officialDir $mName
            if ((Test-Path $srcModel) -and (-not (Test-Path $dstModel))) {
                Log "  Copying model $mName to bundle..."
                Copy-Item $srcModel $dstModel -Recurse -Force
            }
        }
    }
} else {
    Log "WARNING: Cannot pre-download models -- venv python or script not found"
}
$modelSize = (Get-ChildItem $modelsDir -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
Log "Models directory size: $([math]::Round($modelSize, 1)) MB"

# ==========================================================================
# 4. POSTGRESQL PORTABLE
# ==========================================================================
$pgsqlDir = Join-Path $BundleDir "pgsql"
$pgZipUrl = "https://get.enterprisedb.com/postgresql/postgresql-$PgVersion-windows-x64-binaries.zip"
$pgZip    = Join-Path $BundleDir "pgsql-portable.zip"

if (-not (Test-Path (Join-Path (Join-Path $pgsqlDir "bin") "pg_ctl.exe"))) {
    Log "Downloading PostgreSQL $PgVersion portable binaries..."
    Invoke-WebRequest -Uri $pgZipUrl -OutFile $pgZip -UseBasicParsing
    Log "Extracting PostgreSQL..."
    Expand-Archive -Path $pgZip -DestinationPath $BundleDir -Force
    Remove-Item $pgZip -ErrorAction SilentlyContinue

    $initdb = Join-Path (Join-Path $pgsqlDir "bin") "initdb.exe"
    $dataDir = Join-Path $pgsqlDir "data"
    if (Test-Path $initdb) {
        Log "Initializing PostgreSQL data directory..."
        $oldEAP3 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $initdb -D $dataDir -U postgres -E UTF8 --locale=C 2>&1 | ForEach-Object { Log "  $_" }
        $ErrorActionPreference = $oldEAP3

        # Configure pg_hba.conf for local trust auth
        $hbaPath = Join-Path $dataDir "pg_hba.conf"
        $hbaLines = @(
            "# TYPE  DATABASE        USER            ADDRESS                 METHOD",
            "local   all             all                                     trust",
            "host    all             all             127.0.0.1/32            trust",
            "host    all             all             ::1/128                 trust"
        )
        $hbaLines | Set-Content -Path $hbaPath -Encoding UTF8

        # Configure postgresql.conf for desktop use
        $confPath = Join-Path $dataDir "postgresql.conf"
        $pgConf = @(
            "",
            "# NeuroX desktop configuration",
            "listen_addresses = '127.0.0.1'",
            "port = 5432",
            "max_connections = 20",
            "shared_buffers = 128MB",
            "work_mem = 4MB",
            "logging_collector = on",
            "log_directory = 'log'",
            "log_filename = 'postgresql-%Y-%m-%d.log'",
            "log_rotation_age = 1d",
            "log_rotation_size = 10MB"
        )
        Add-Content -Path $confPath -Value ($pgConf -join "`r`n")
        Log "PostgreSQL initialized with local trust authentication"
    }
} else {
    Log "PostgreSQL portable already present -- skipping"
}

# ==========================================================================
# 4b. LIBREOFFICE PORTABLE (DOCX -> PDF conversion via headless soffice)
# ==========================================================================
# We extract from the official LibreOffice MSI using msiexec /a (admin install,
# no actual install on the build machine). Result: program/soffice.exe + share/.
$loDir   = Join-Path $BundleDir "libreoffice"
$loVer   = "25.8.6"
$loMsiUrl = "https://download.documentfoundation.org/libreoffice/stable/$loVer/win/x86_64/LibreOffice_${loVer}_Win_x86-64.msi"
$loMsi   = Join-Path $BundleDir "libreoffice.msi"
$loExtract = Join-Path $BundleDir "libreoffice_extract"

if (-not (Test-Path (Join-Path $loDir "program\soffice.exe"))) {
    Log "Downloading LibreOffice $loVer (~340 MB) ..."
    Invoke-WebRequest -Uri $loMsiUrl -OutFile $loMsi -UseBasicParsing
    Log "Extracting LibreOffice MSI (admin install) ..."
    if (Test-Path $loExtract) { Remove-Item -Recurse -Force $loExtract }
    New-Item -ItemType Directory -Force $loExtract | Out-Null
    & msiexec.exe /a "$loMsi" /qn TARGETDIR="$loExtract" 2>&1 | ForEach-Object { Log "  msi: $_" }

    # Result tree: $loExtract\LibreOffice\program\soffice.exe + share\
    $loRoot = Join-Path $loExtract "LibreOffice"
    if (-not (Test-Path (Join-Path $loRoot "program\soffice.exe"))) {
        # Some MSI versions extract directly without the LibreOffice/ wrapper
        $loRoot = $loExtract
    }
    if (Test-Path (Join-Path $loRoot "program\soffice.exe")) {
        if (Test-Path $loDir) { Remove-Item -Recurse -Force $loDir }
        New-Item -ItemType Directory -Force $loDir | Out-Null
        # Copy contents of extracted root, excluding the MSI itself
        Get-ChildItem $loRoot -Exclude "libreoffice.msi","*.msi" |
            Copy-Item -Destination $loDir -Recurse -Force

        # Trim subfolders we don't need for headless PDF conversion.
        # share\extensions (~460 MB: dictionaries, language tools, java extensions)
        # and program\resource\* (UI translations, ~260 MB; keep en-US + fr only)
        # are not needed for DOCX->PDF rendering. Trim verified safe by smoke test.
        foreach ($trim in @("help", "readmes", "share\Scripts", "share\gallery", "share\samples", "share\template", "share\extensions")) {
            $tp = Join-Path $loDir $trim
            if (Test-Path $tp) {
                Log "  trimming $trim"
                Remove-Item -Recurse -Force $tp
            }
        }

        # Trim program\resource: keep only en-US and fr UI translation .res files
        $resDir = Join-Path $loDir "program\resource"
        if (Test-Path $resDir) {
            Log "  trimming program\resource (keep en-US, fr)"
            Get-ChildItem $resDir -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notin @('en-US','fr') } |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Get-ChildItem $resDir -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notmatch '_(en-US|fr)\.res$' } |
                Remove-Item -Force -ErrorAction SilentlyContinue
        }
        Log "LibreOffice runtime placed in $loDir"
    } else {
        Log "WARNING: soffice.exe not found after MSI extract -- DOCX->PDF will fail"
    }

    Remove-Item $loMsi -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $loExtract -ErrorAction SilentlyContinue
} else {
    Log "LibreOffice portable already present -- skipping"
}

# ==========================================================================
# 5. COPY BACKEND SOURCE
# ==========================================================================
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

# ==========================================================================
# 6. BUILD ELECTRON FRONTEND
# ==========================================================================
$frontendDir = Join-Path $RepoRoot "Neuro_frontend"
$frontendDist = Join-Path $BundleDir "frontend"

Log "Building Electron frontend (win-unpacked)..."
Push-Location $frontendDir
try {
    $oldEAP2 = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & npx electron-vite build 2>&1 | ForEach-Object { Log "  $_" }
    & npx electron-builder --win --dir 2>&1 | ForEach-Object { Log "  $_" }
    $ErrorActionPreference = $oldEAP2
    $unpackedDir = Join-Path (Join-Path $frontendDir "dist") "win-unpacked"
    if (Test-Path $unpackedDir) {
        Copy-Item "$unpackedDir\*" $frontendDist -Recurse -Force
        Log "Frontend built and copied to bundle"
    } else {
        Log "WARNING: win-unpacked not found -- frontend build may have failed"
    }
} finally {
    Pop-Location
}

# ==========================================================================
# 7. CREATE .ENV TEMPLATE FOR PRODUCTION
# ==========================================================================
$envTemplate = Join-Path $backendSrc ".env"
$envLines = @(
    "# NeuroX Production Configuration",
    "DATABASE_URL=postgresql://postgres@localhost:5432/neurox",
    "CORS_ORIGINS=*",
    "LOG_LEVEL=INFO",
    "CENTER_NAME=CDS OPHTALMOLOGIE NANTERRE LA BOULE",
    "CENTER_ADDRESS=123 Avenue de la Republique, 92000 Nanterre",
    "CENTER_TEL=01 47 00 00 00",
    "CENTER_EMAIL=contact@cds-nanterre.fr",
    "CENTER_FINESS=920036563",
    "CENTER_CITY=Nanterre",
    "EDM_BASE_PATH=C:/temp/fse_ocr",
    "GALAXIE_EDM=D:/Stimut/Documents_Patients"
)
$envLines | Set-Content -Path $envTemplate -Encoding UTF8
Log "Production .env template created"

# ==========================================================================
# SUMMARY
# ==========================================================================
$totalSize = (Get-ChildItem $BundleDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Log "================================================================="
Log "Bundle complete: $([math]::Round($totalSize, 0)) MB total"
Log "  Python:     $(Join-Path $BundleDir 'python')"
Log "  Wheels:     $wheelCount packages"
Log "  Models:     $([math]::Round($modelSize, 1)) MB"
Log "  PostgreSQL: $(Join-Path $BundleDir 'pgsql')"
Log "  Frontend:   $(Join-Path $BundleDir 'frontend')"
Log "  Backend:    $(Join-Path $BundleDir 'backend_src')"
Log "================================================================="
Log "Next: compile installer\NeuroX_Installer.iss with Inno Setup"
