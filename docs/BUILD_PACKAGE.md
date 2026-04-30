# NeuroX – Building a New Installer Package

This guide walks you through producing a new `NeuroX-X.Y.Z-Setup.exe` from a clean
checkout of the `Ihebdhouibi/neuro` monorepo on Windows 10/11 x64.

End result: one self-contained `.exe` (~580 MB) that installs the Electron
frontend, the Python FastAPI backend, an embedded Python 3.11, a portable
PostgreSQL 17.4, and the RapidOCR ONNX models — fully offline.

---

## 1. One-time machine setup

You only need to do this once per developer machine.

### 1.1 Required tools

| Tool                | Version                | Where to get it                                                    |
| ------------------- | ---------------------- | ------------------------------------------------------------------ |
| Git                 | any                    | https://git-scm.com/download/win                                   |
| Node.js             | 20 LTS or newer        | https://nodejs.org/                                                |
| Python              | 3.11.x (matching pyenv) | https://www.python.org/downloads/                                  |
| Inno Setup          | 6.x                    | https://jrsoftware.org/isdl.php                                    |
| Visual C++ Redist   | x64                    | bundled in `installer/bundle/vc_redist.x64.exe` (auto-fetched)     |

Verify:

```powershell
node --version          # v20+
python --version        # 3.11.x
git --version
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\iscc.exe" /?   # should print Inno help
```

### 1.2 Enable Windows Developer Mode (mandatory)

`electron-builder` extracts a `winCodeSign` archive that contains macOS
symlinks. Without Developer Mode, extraction fails with:

```
ERROR: Cannot create symbolic link : Le client ne dispose pas d'un privilège
```

Fix once and forget:

1. Open **Settings → Système → Pour les développeurs**, or run
   `ms-settings:developers` in the Run dialog (`Win+R`).
2. Toggle **Mode développeur** ON.
3. Confirm the prompt. No reboot required.
4. **Close and reopen any PowerShell** so the new privilege propagates.

### 1.3 Clone & install dependencies

```powershell
cd D:\Projects                        # or wherever you keep code
git clone https://github.com/Ihebdhouibi/neuro.git
cd neuro

# Frontend deps
cd Neuro_frontend
npm install
cd ..

# Backend venv (used by download_deps.ps1 to harvest wheels)
cd Neuro_backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate
cd ..
```

---

## 2. Per-build workflow

Run from the **repo root** (`D:\Projects\neuro`) for every new release.

### 2.1 Pull latest code

```powershell
cd D:\Projects\neuro
git checkout feature/b2-manual-modes      # or whichever branch you ship
git pull
```

### 2.2 Bump the version

Edit `installer/NeuroX_Installer.iss` and change:

```ini
#define MyAppVersion   "1.0.9"
```

(The frontend `package.json` version is a template default — leave it alone.
The release version of record is in the `.iss`.)

### 2.3 Build the Electron frontend

```powershell
cd Neuro_frontend
npx electron-vite build                  # transpile + bundle (~30 s)
$env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
npx electron-builder --win --dir         # produces dist\win-unpacked (~3 min)
cd ..
```

Expected output: `Neuro_frontend\dist\win-unpacked\ElectronReactApp.exe` (~195 MB).

> If you get the `Cannot create symbolic link` error: you skipped step 1.2.
> Enable Dev Mode and reopen the terminal.

### 2.4 Refresh the installer bundle

#### First-time only (or when dependencies change)

The bundle holds heavy assets (Python embed, wheels, models, PostgreSQL).
If `installer\bundle\` is empty or older than the last `requirements.txt`
change, run:

```powershell
cd D:\Projects\neuro
.\installer\download_deps.ps1            # ~10 min, ~1 GB download
```

That script downloads everything into `installer\bundle\` and also rebuilds
the frontend, so you can skip 2.3 if you go this route.

#### For every code-only rebuild

Just refresh frontend + backend source in the existing bundle:

```powershell
$bundle = "D:\Projects\neuro\installer\bundle"
$unpacked = "D:\Projects\neuro\Neuro_frontend\dist\win-unpacked"

# Frontend
Remove-Item -Recurse -Force "$bundle\frontend\*" -ErrorAction SilentlyContinue
Copy-Item "$unpacked\*" "$bundle\frontend\" -Recurse -Force

# Backend source
$src = "D:\Projects\neuro\Neuro_backend"
foreach ($item in @('api','templates','database.py','fill_template.py',
    'ocr_filter.py','ocr_to_schema.py','openai_extraction.py',
    'prescription_generator.py','preprocess_for_ocr.py','practitioners.py',
    'requirements.txt','sample_schema.json','init_db.py',
    'init_medical_lists.py','medical_lists_seed.sql')) {
    $s = Join-Path $src $item; $d = Join-Path "$bundle\backend_src" $item
    if (Test-Path $s) {
        if ((Get-Item $s).PSIsContainer) {
            Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
            Copy-Item $s $d -Recurse -Force
        } else { Copy-Item $s $d -Force }
    }
}

# Strip Python cache (otherwise embedded in the installer)
Get-ChildItem "$bundle\backend_src" -Filter __pycache__ -Recurse -Directory |
    Remove-Item -Recurse -Force
```

Sanity check the bundle:

```powershell
foreach ($d in 'frontend','python','wheels','models','pgsql','backend_src') {
    $sz = (Get-ChildItem "$bundle\$d" -Recurse -EA 0 |
        Measure-Object Length -Sum).Sum / 1MB
    "{0,-15} {1,8:N1} MB" -f $d, $sz
}
```

Expected order of magnitude:

```
frontend          ~466 MB
python            ~424 MB
wheels            ~122 MB
models             ~28 MB
pgsql             ~851 MB
backend_src        ~1   MB
```

### 2.5 Compile the installer

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\iscc.exe" `
    "D:\Projects\neuro\installer\NeuroX_Installer.iss"
```

Compilation takes **25–30 minutes** on a typical laptop (LZMA2 ultra64 solid
on ~1.9 GB). Don't kill it.

While running, you can monitor progress:

```powershell
while (Get-Process iscc -EA SilentlyContinue) {
    Start-Sleep 30
    $f = Get-Item D:\Projects\neuro\installer\output\NeuroX-*-Setup.exe -EA 0
    "[$(Get-Date -Format 'HH:mm:ss')] $([math]::Round($f.Length/1MB,1)) MB"
}
"DONE"
```

### 2.6 Verify the output

```powershell
Get-ChildItem D:\Projects\neuro\installer\output\*.exe |
    Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

Expected:

```
NeuroX-1.0.9-Setup.exe   ~580 MB
```

If it's much smaller (< 100 MB), the build was killed mid-way — re-run 2.5.

---

## 3. Smoke-test before sharing

1. Copy the `.exe` to a clean Windows 10/11 VM (or another laptop).
2. Run as administrator (it registers PostgreSQL).
3. After install, launch from Start Menu → "NeuroX".
4. The splash window should appear, the bundled PostgreSQL service should be
   running, and the FastAPI backend should respond on
   `http://localhost:7861/`.
5. Sign up a user, then sign in with recovery passphrase to confirm
   end-to-end auth flow.

Logs to inspect when something goes wrong:

| Path                                        | What                          |
| ------------------------------------------- | ----------------------------- |
| `%LOCALAPPDATA%\NeuroX\logs\frontend.log`   | Electron main + renderer      |
| `<install-dir>\logs\backend.log`            | Python FastAPI                |
| `<install-dir>\pgsql\data\log\*.log`        | PostgreSQL                    |
| `<install-dir>\logs\inno_install.log`       | Setup-time log                |

---

## 4. Commit & push

After a successful build, commit any version bumps and tag the release:

```powershell
cd D:\Projects\neuro
git add installer/NeuroX_Installer.iss
git commit -m "release: v1.0.9"
git tag v1.0.9
git push origin feature/b2-manual-modes --tags
```

Upload `installer\output\NeuroX-1.0.9-Setup.exe` to the GitHub Release page
(or wherever you distribute) — it's too big for git.

---

## 5. Troubleshooting cheatsheet

| Symptom                                             | Cause / Fix                                                                        |
| --------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `Cannot create symbolic link` during builder        | Dev Mode off → enable per **1.2**, reopen terminal                                 |
| Setup .exe is only ~40 MB                           | iscc still running. Wait until `Get-Process iscc` returns nothing                  |
| `tsconfig.web.json … Invalid value for --ignoreDeprecations` | Pre-existing, harmless. `electron-vite build` works regardless                |
| Backend doesn't start after install                 | Check `<install-dir>\logs\backend.log` for missing wheels / DLL                    |
| PostgreSQL port 5432 already in use                 | Stop any other Postgres service before launching NeuroX                            |
| `winCodeSign` keeps failing even with Dev Mode      | Wipe cache: `Remove-Item -Recurse -Force "$env:LOCALAPPDATA\electron-builder"`     |
| Inno warns about missing files                      | Re-run `installer\download_deps.ps1` to repopulate the bundle                      |

---

## 6. What lives where (mental map)

```
neuro/
├── Neuro_frontend/          # Electron + React app
│   ├── app/                 # React renderer (TSX)
│   ├── lib/main/            # Electron main process (TS)
│   ├── package.json
│   ├── electron-builder.yml
│   └── dist/win-unpacked/   # produced by step 2.3
├── Neuro_backend/           # FastAPI + RapidOCR
│   ├── api/main_paddleocr.py
│   ├── requirements.txt
│   └── venv/                # local dev venv
└── installer/
    ├── NeuroX_Installer.iss # Inno Setup script
    ├── download_deps.ps1    # populates bundle/
    ├── bundle/              # everything the installer ships (~1.9 GB)
    │   ├── frontend/        # ← refreshed every build
    │   ├── backend_src/     # ← refreshed every build
    │   ├── python/          # embedded CPython 3.11
    │   ├── wheels/          # offline pip cache
    │   ├── models/          # RapidOCR ONNX models
    │   └── pgsql/           # portable PostgreSQL 17.4
    └── output/              # final NeuroX-X.Y.Z-Setup.exe lands here
```
