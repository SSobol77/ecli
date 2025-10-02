<#
.SYNOPSIS
Builds and packages ECLI for Windows (x64) using PyInstaller → NSIS,
producing STRICT, versioned artifacts under releases/<version>/.

.DESCRIPTION
This script is the canonical Windows packager for ECLI. It:
  1) Reads <version> from pyproject.toml ([project].version).
  2) Builds a single-file executable with PyInstaller (via `uv run`).
  3) Invokes NSIS (makensis) to produce an installer (EXE) with strict naming.
  4) Writes a SHA-256 sidecar file next to the installer.
  5) Asserts that outputs exist in the exact paths.

STRICT OUTPUTS (normalized)
  releases\<version>\ecli_<version>_win_x64.exe
  releases\<version>\ecli_<version>_win_x64.exe.sha256

The script follows the same dependency stack and hidden-import rules used on
Linux/FreeBSD to ensure consistent runtime behavior across platforms.

.REQUIREMENTS
  - OS: Windows 10/11 x64
  - Python 3.11 (x64) on PATH
  - uv (recommended) for reproducible dependency execution
    * Install: `pipx install uv`  or  `pip install uv`
  - NSIS (makensis) on PATH
    * Install (Chocolatey):  `choco install nsis -y`
  - Tools available:
    * PowerShell 7+ (pwsh)  — recommended
    * Git (for typical workflows)

.ARTIFACTS
  Path:    releases\<version>\
  Files:   ecli_<version>_win_x64.exe
           ecli_<version>_win_x64.exe.sha256
  Version: extracted from pyproject.toml → [project].version

.USAGE
  # From the repo root (recommended)
  pwsh -File scripts/build_pyinstaller_windows.ps1

  # If called from elsewhere:
  #   Ensure you run the script located in <repo>/scripts/
  pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\repo\scripts\build_pyinstaller_windows.ps1"

.EXAMPLES
  EXAMPLE 1: Local build on a developer workstation
    PS> pwsh -File scripts/build_pyinstaller_windows.ps1
    PS> Get-Item releases\*\ecli_*_win_x64.exe*
    PS> Get-FileHash -Algorithm SHA256 releases\0.1.0\ecli_0.1.0_win_x64.exe

  EXAMPLE 2: Makefile workflow (from bash on Windows, e.g., Git Bash)
    $ make package-windows
    $ make show-windows-artifacts
    $ make release-windows     # uploads to GitHub Release (requires gh)

  EXAMPLE 3: GitHub Actions step (excerpt)
    - name: Setup Python 3.11
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
        architecture: "x64"
    - name: Install NSIS
      run: choco install nsis -y
    - name: Build Windows installer
      shell: pwsh
      run: ./scripts/build_pyinstaller_windows.ps1
    - name: Upload artifacts
      uses: actions/upload-artifact@v4
      with:
        name: windows-installer
        path: |
          releases/${{ steps.ver.outputs.version }}/ecli_${{ steps.ver.outputs.version }}_win_x64.exe
          releases/${{ steps.ver.outputs.version }}/ecli_${{ steps.ver.outputs.version }}_win_x64.exe.sha256

.VERIFICATION
  # Verify the installer exists in the STRICT location:
  PS> Test-Path releases\<version>\ecli_<version>_win_x64.exe

  # Verify checksum matches:
  PS> (Get-FileHash -Algorithm SHA256 releases\<version>\ecli_<version>_win_x64.exe).Hash
  PS> Get-Content releases\<version>\ecli_<version>_win_x64.exe.sha256

.TROUBLESHOOTING
  - "NSIS not found":
      Ensure `makensis` is on PATH. Install via Chocolatey:
        choco install nsis -y
  - "PyInstaller output not found":
      Check that Python 3.11 (x64) is the default `python`, or use `py -3.11`.
      Ensure uv is installed and `uv run` works:
        pipx install uv   # or pip install uv
  - "Missing hidden imports at runtime":
      The script passes explicit --hidden-import/--collect-all for the aiohttp stack,
      dotenv, toml, PyYAML, pygments, wcwidth, etc. If you add libraries that
      use dynamic imports, update the PyInstaller call accordingly.
  - "Artifacts are not in releases/<version>/":
      The script fails fast if the strict paths are missing. Inspect console output,
      verify `pyproject.toml` version, and confirm NSIS wrote to the OUTFILE.

.EXIT CODES
  0  Success
  1  Version probing or PyInstaller failure
  2  Installer was not produced at the strict OUTFILE path
  3  SHA256 sidecar file was not created

.NOTES
  - The script is intentionally parameterless: it derives <version> from
    pyproject.toml and normalizes the output naming and location to keep Windows
    packaging consistent with Linux and FreeBSD builds.
  - For code signing (signtool) integration, add a post-build signing step
    before checksum generation and ensure your certificate/secrets are available.

.LINK
  FreeBSD/Linux packagers use the same dependency stack and strict naming rules.
  See: scripts/build-and-package-freebsd.sh, scripts/build-and-package-deb.sh,
       scripts/build-and-package-rpm.sh
#>


#Requires -Version 7
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "OK  $m" -ForegroundColor Green }
function Err($m){ Write-Host "ERR $m" -ForegroundColor Red }

# Paths
$PROJECT_ROOT = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $PROJECT_ROOT

# Read version from pyproject.toml
Info "Reading version from pyproject.toml..."
$version = (Get-Content pyproject.toml) -match '^\s*version\s*=\s*"(.*)"' | ForEach-Object {
    ($_ -replace '^\s*version\s*=\s*"(.*)".*','$1')
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($version)) { Err "Cannot read version"; exit 1 }
Ok "Version: $version"

$ARCH = "win_x64"
$releasesDir = Join-Path "releases" $version
$outInstaller = Join-Path $releasesDir ("ecli_{0}_{1}.exe" -f $version,$ARCH)
$outSha = "$outInstaller.sha256"

# Output dirs for PyInstaller
$outDir = Join-Path $PROJECT_ROOT "build\windows"
New-Item -ItemType Directory -Force -Path "$outDir\dist" | Out-Null
New-Item -ItemType Directory -Force -Path "$outDir\work" | Out-Null

# Ensure deps via uv (matches Linux/FreeBSD stacks)
Info "Syncing Python deps with uv..."
uv sync --frozen

Info "Building executable with PyInstaller via uv run..."
uv run pyinstaller `
  --name ecli `
  --onefile `
  --console `
  --clean `
  --strip `
  --distpath "$outDir\dist" `
  --workpath "$outDir\work" `
  --paths "$($PROJECT_ROOT)\src" `
  --add-data "$($PROJECT_ROOT)\config.toml;." `
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
  "$($PROJECT_ROOT)\src\ecli\__main__.py"

$exeBuilt = Join-Path $outDir "dist\ecli.exe"
if (-not (Test-Path $exeBuilt)) { Err "PyInstaller output not found: $exeBuilt"; exit 1 }
Ok "Built binary: $exeBuilt"

# NSIS packaging
if (-not (Get-Command makensis -ErrorAction SilentlyContinue)) {
  Err "NSIS (makensis) not found in PATH. Install: choco install nsis"
  exit 1
}

# Ensure releases dir
New-Item -ItemType Directory -Force -Path $releasesDir | Out-Null

# Build installer with strict OUTFILE and defines
$nsis = "packaging/windows/nsis/ecli.nsi"
$defines = @(
  "/DVERSION=$version"
  "/DOUTFILE=$outInstaller"
  "/DINPUT_EXE=$exeBuilt"
)
Info "Running makensis..."
& makensis $defines $nsis | Write-Host

if (-not (Test-Path $outInstaller)) {
  Err "Installer not produced at $outInstaller"
  exit 2
}

# SHA256 sidecar
Info "Writing SHA256..."
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outInstaller).Hash
$hash | Out-File -Encoding ascii -NoNewline $outSha

# Assertions
if (-not (Test-Path $outSha)) { Err "Missing checksum $outSha"; exit 3 }

Ok "Installer: $outInstaller"
Ok "Checksum:  $outSha"
Info "Done."
