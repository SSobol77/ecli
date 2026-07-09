# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build-and-package-windows.ps1
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

<#
.SYNOPSIS
Builds ECLI Windows x86_64 release artifacts.

.DESCRIPTION
The canonical Windows packager emits two unsigned artifacts:

  releases\<version>\ecli_<version>_win_x86_64.exe
  releases\<version>\ecli_<version>_win_x86_64_setup.exe

Both artifacts receive coreutils-format SHA256 sidecars with ASCII-compatible
bytes and an explicit LF terminator. The portable executable is built before
the NSIS installer packaging step.
#>

$ErrorActionPreference = "Stop"

function Write-Info($Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "OK  $Message" -ForegroundColor Green }
function Write-Err($Message) { Write-Host "ERR $Message" -ForegroundColor Red }

function Write-AsciiLfFile($Path, $Content) {
  $directory = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
  }
  $encoding = [System.Text.ASCIIEncoding]::new()
  [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Write-Sha256Sidecar($ArtifactPath) {
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArtifactPath).Hash.ToLowerInvariant()
  $basename = Split-Path $ArtifactPath -Leaf
  Write-AsciiLfFile -Path "$ArtifactPath.sha256" -Content ("{0}  {1}`n" -f $hash, $basename)
}

function Split-F4ToolList($Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return @()
  }
  return ($Value -split '[,;\s]+' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Invoke-F4LinterEvidenceHook($ArtifactId) {
  $mode = if ([string]::IsNullOrWhiteSpace($env:ECLI_F4_LINTER_PROVISIONING_MODE)) {
    "dry-run"
  } else {
    $env:ECLI_F4_LINTER_PROVISIONING_MODE
  }
  $profile = if ([string]::IsNullOrWhiteSpace($env:ECLI_F4_LINTER_PROFILE)) {
    "full"
  } else {
    $env:ECLI_F4_LINTER_PROFILE
  }
  $targetDir = Join-Path $projectRoot "build\f4-linter-provisioning\$ArtifactId\target"
  $evidenceDir = Join-Path $projectRoot "build\f4-linter-provisioning\$ArtifactId\evidence"
  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
  New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

  $provisionArgs = @(
    "scripts/provision_f4_linters.py",
    "--artifact", $ArtifactId,
    "--target-dir", $targetDir,
    "--evidence-dir", $evidenceDir,
    "--mode", $mode,
    "--profile", $profile,
    "--json"
  )
  foreach ($tool in Split-F4ToolList $env:ECLI_F4_LINTER_INCLUDE_TOOLS) {
    $provisionArgs += @("--include-tool", $tool)
  }
  foreach ($tool in Split-F4ToolList $env:ECLI_F4_LINTER_EXCLUDE_TOOLS) {
    $provisionArgs += @("--exclude-tool", $tool)
  }
  if (-not [string]::IsNullOrWhiteSpace($env:ECLI_F4_LINTER_SELECTION_JSON)) {
    $provisionArgs += @("--selection-json", $env:ECLI_F4_LINTER_SELECTION_JSON)
  }

  Write-Info "Running F4 provisioning evidence gate for $ArtifactId..."
  python @provisionArgs
  if ($LASTEXITCODE -ne 0) {
    Write-Err "F4 linter evidence generation failed for $ArtifactId"
    exit $LASTEXITCODE
  }

  python scripts/verify_f4_linter_provisioning.py --artifact $ArtifactId --evidence-dir $evidenceDir
  if ($LASTEXITCODE -ne 0) {
    Write-Err "F4 linter evidence verification failed for $ArtifactId"
    exit $LASTEXITCODE
  }
}

function Resolve-MakeNsis {
  $command = Get-Command makensis -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }

  $candidates = @()
  if ($env:ProgramFiles) {
    $candidates += (Join-Path $env:ProgramFiles "NSIS\makensis.exe")
  }
  $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
  if ($programFilesX86) {
    $candidates += (Join-Path $programFilesX86 "NSIS\makensis.exe")
  }

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }

  return $null
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

Write-Info "Reading version from pyproject.toml..."
$version = (Get-Content pyproject.toml) -match '^\s*version\s*=\s*"(.*)"' | ForEach-Object {
  ($_ -replace '^\s*version\s*=\s*"(.*)".*', '$1')
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($version)) {
  Write-Err "Cannot read version"
  exit 1
}
Write-Ok "Version: $version"

Write-Info "Checking production runtime imports..."
python scripts/check_runtime_imports.py

$winArch = "x86_64"
$releaseDir = Join-Path "releases" $version
$portableName = "ecli_${version}_win_${winArch}.exe"
$installerName = "ecli_${version}_win_${winArch}_setup.exe"
$portablePath = Join-Path $releaseDir $portableName
$installerPath = Join-Path $releaseDir $installerName
$portableFullPath = Join-Path $projectRoot.Path $portablePath
$installerFullPath = Join-Path $projectRoot.Path $installerPath
$buildRoot = Join-Path $projectRoot "build\windows"
$distDir = Join-Path $buildRoot "dist"
$workDir = Join-Path $buildRoot "work"
$specPath = Join-Path $projectRoot "packaging\pyinstaller\ecli.spec"
$iconPath = Join-Path $projectRoot "img\logo_m.ico"

if (-not (Test-Path -LiteralPath $specPath)) {
  Write-Err "Missing canonical PyInstaller spec: $specPath"
  exit 1
}

Write-Info "Ensuring Python dependencies..."
python -m pip install --upgrade pip wheel setuptools | Out-Null
python -m pip install -e ".[dev]" | Out-Null

Write-Info "Cleaning Windows build directories..."
Remove-Item -Recurse -Force $buildRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $distDir | Out-Null
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

Write-Info "Building portable executable with PyInstaller spec..."
$env:ECLI_REPO_ROOT = $projectRoot.Path
python -m PyInstaller `
  $specPath `
  --clean `
  --noconfirm `
  --distpath $distDir `
  --workpath $workDir

$builtExe = Join-Path $distDir "ecli.exe"
if (-not (Test-Path -LiteralPath $builtExe)) {
  Write-Err "PyInstaller output not found: $builtExe"
  exit 1
}
Copy-Item -LiteralPath $builtExe -Destination $portablePath -Force
Write-Ok "Portable executable: $portablePath"

Write-Info "Writing portable SHA256..."
Write-Sha256Sidecar -ArtifactPath $portablePath

Write-Info "Smoke-testing portable executable help/version..."
$smokeHome = Join-Path $buildRoot "smoke-home"
New-Item -ItemType Directory -Force -Path $smokeHome | Out-Null
$oldUserProfile = $env:USERPROFILE
$oldHome = $env:HOME
try {
  $env:USERPROFILE = $smokeHome
  $env:HOME = $smokeHome
  $helpOutput = & $portableFullPath --help
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($helpOutput -join "`n"))) {
    Write-Err "Portable executable --help smoke failed."
    exit 4
  }
  $versionOutput = (& $portableFullPath --version) -join "`n"
  if ($LASTEXITCODE -ne 0 -or $versionOutput.Trim() -ne "ecli $version") {
    Write-Err "Portable executable --version smoke failed: '$versionOutput'"
    exit 4
  }
}
finally {
  $env:USERPROFILE = $oldUserProfile
  $env:HOME = $oldHome
}
Write-Ok "Portable executable help/version smoke passed."

$makensis = Resolve-MakeNsis
if (-not $makensis) {
  Write-Err "NSIS (makensis) not found. Install NSIS or add makensis.exe to PATH."
  exit 1
}

Write-Info "Building NSIS installer..."
$nsisScript = Join-Path $projectRoot "packaging\windows\nsis\ecli.nsi"
$nsisDefines = @(
  "/DVERSION=$version",
  "/DOUTFILE=$installerFullPath",
  "/DINPUT_EXE=$portableFullPath"
)
if (Test-Path -LiteralPath $iconPath) {
  $nsisDefines += "/DICON_ICO=$iconPath"
}
& $makensis $nsisDefines $nsisScript

if (-not (Test-Path -LiteralPath $installerPath)) {
  Write-Err "Installer not produced at $installerPath"
  exit 2
}
Write-Ok "Installer: $installerPath"

Write-Info "Writing installer SHA256..."
Write-Sha256Sidecar -ArtifactPath $installerPath

Invoke-F4LinterEvidenceHook "windows-portable-exe"
Invoke-F4LinterEvidenceHook "windows-nsis-installer"

$envPath = Join-Path $releaseDir ".win.env"
Write-AsciiLfFile -Path $envPath -Content (
  "WIN_ARCH=x86_64`n" +
  "WIN_PORTABLE_FILENAME=$portableName`n" +
  "WIN_INSTALLER_FILENAME=$installerName`n"
)

foreach ($path in @($portablePath, "$portablePath.sha256", $installerPath, "$installerPath.sha256", $envPath)) {
  if (-not (Test-Path -LiteralPath $path)) {
    Write-Err "Missing expected output: $path"
    exit 3
  }
}

Write-Ok "Portable checksum: $portablePath.sha256"
Write-Ok "Installer checksum: $installerPath.sha256"
Write-Ok "Environment file: $envPath"
Write-Info "Done."
