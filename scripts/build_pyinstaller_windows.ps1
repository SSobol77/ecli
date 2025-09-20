#Requires -Version 7
$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Join-Path $PSScriptRoot ".." | Resolve-Path
$OUT_DIR = Join-Path $PROJECT_ROOT "build\windows"
New-Item -ItemType Directory -Force -Path "$OUT_DIR\dist" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT_DIR\work" | Out-Null

uv sync --frozen
uv run pyinstaller `
  --name ecli `
  --onefile `
  --console `
  --clean `
  --distpath "$OUT_DIR\dist" `
  --workpath "$OUT_DIR\work" `
  --paths "$($PROJECT_ROOT)\src" `
  "$($PROJECT_ROOT)\src\ecli\__main__.py"

Write-Host "Built binary: $OUT_DIR\dist\ecli.exe"
