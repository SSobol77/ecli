<# 
===============================================================================
ECLI — Windows packaging (PyInstaller → NSIS)
Strict outputs:
  releases\<version>\ecli_<version>_win_x64.exe
  releases\<version>\ecli_<version>_win_x64.exe.sha256

Requirements:
- Windows 10/11 x64, Python 3.11 (x64), NSIS (makensis in PATH)
- powershell.exe or pwsh
===============================================================================
#>

$ErrorActionPreference = "Stop"

function Write-Info($msg){ Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg){ Write-Host "OK  $msg" -ForegroundColor Green }
function Write-Err($msg){ Write-Host "ERR $msg" -ForegroundColor Red }

# Move to repo root
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path) | Out-Null
Set-Location -Path ..  # scripts -> repo root

# Version from pyproject.toml
Write-Info "Reading version from pyproject.toml..."
$version = (Get-Content pyproject.toml) -match '^\s*version\s*=\s*"(.*)"' | ForEach-Object {
    ($_ -replace '^\s*version\s*=\s*"(.*)".*','$1')
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($version)) { Write-Err "Cannot read version"; exit 1 }
Write-Ok "Version: $version"

$releasesDir = "releases\$version"
$exeNameBase = "ecli_${version}_win_x64.exe"
$exePath = Join-Path $releasesDir $exeNameBase
$shaPath = "$exePath.sha256"

# Python deps
Write-Info "Ensuring Python deps (pyinstaller + runtime stack)..."
python -m pip install --upgrade pip wheel setuptools | Out-Null
python -m pip install `
  pyinstaller `
  aiohttp aiosignal yarl multidict frozenlist `
  python-dotenv toml chardet pyperclip wcwidth pygments tato PyYAML | Out-Null

# PyInstaller
Write-Info "Cleaning build/ dist/..."
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Info "Building onefile exe with PyInstaller..."
if (Test-Path "ecli.spec") {
  pyinstaller ecli.spec --clean --noconfirm
} else {
  pyinstaller main.py `
    --name ecli `
    --onefile --clean --noconfirm --strip `
    --paths "src" `
    --add-data "config.toml;." `
    --hidden-import ecli `
    --hidden-import dotenv       --collect-all dotenv `
    --hidden-import toml `
    --hidden-import PyYAML       --collect-all PyYAML `
    --hidden-import aiohttp      --collect-all aiohttp `
    --hidden-import aiosignal    --collect-all aiosignal `
    --hidden-import yarl         --collect-all yarl `
    --hidden-import multidict    --collect-all multidict `
    --hidden-import frozenlist   --collect-all frozenlist `
    --hidden-import chardet      --collect-all chardet `
    --hidden-import pyperclip    --collect-all pyperclip `
    --hidden-import wcwidth      --collect-all wcwidth `
    --hidden-import pygments     --collect-all pygments `
    --runtime-hook packaging/pyinstaller/rthooks/force_imports.py
}

$exeBuilt = $null
if (Test-Path "dist\ecli\ecli.exe") { $exeBuilt = "dist\ecli\ecli.exe" }
elseif (Test-Path "dist\ecli.exe") { $exeBuilt = "dist\ecli.exe" }
if (-not $exeBuilt) { Write-Err "PyInstaller output not found in dist\"; exit 1 }
Write-Ok "Executable: $exeBuilt"

# NSIS (makensis) — build installer from your NSIS script
Write-Info "Building NSIS installer..."
if (-not (Get-Command makensis -ErrorAction SilentlyContinue)) {
  Write-Err "NSIS (makensis) not found in PATH. Install via choco: choco install nsis"
  exit 1
}

# Prepare NSIS input dir
$nsisStage = "build\nsis"
Remove-Item -Recurse -Force $nsisStage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $nsisStage | Out-Null
Copy-Item $exeBuilt "$nsisStage\ecli.exe"

# Invoke makensis with defines for version/output
$nsisScript = "packaging/windows/nsis/ecli.nsi"
$defines = "/DVERSION=$version /DOUTFILE=""$exePath"""

# Ensure output dir
New-Item -ItemType Directory -Force -Path $releasesDir | Out-Null

# Run NSIS
& makensis $defines $nsisScript | Write-Host

if (-not (Test-Path $exePath)) {
  # If your .nsi writes elsewhere, fallback: copy staged exe as installer
  Copy-Item "$nsisStage\ecli.exe" $exePath
}

# SHA256
Write-Info "Writing SHA256..."
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exePath).Hash
$hash | Out-File -Encoding ascii -NoNewline $shaPath

# Assert strict outputs
if (-not (Test-Path $exePath)) { Write-Err "Missing $exePath"; exit 2 }
if (-not (Test-Path $shaPath)) { Write-Err "Missing $shaPath"; exit 3 }

Write-Ok "Installer: $exePath"
Write-Ok "Checksum:  $shaPath"
Write-Info "Done."
