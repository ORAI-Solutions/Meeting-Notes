Param(
    [switch]$OneFile = $false,
    [switch]$Clean = $false
)

# Build script for Meeting Notes Desktop (GPU-capable)
# - Builds frontend (pnpm build)
# - Syncs Python deps (uv sync)
# - Runs PyInstaller with desktop spec (GPU-capable)

Write-Host "Meeting Notes Desktop Build" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Ensure we are at repo root
if (-not (Test-Path "backend" -PathType Container)) {
    Write-Host "Error: Please run this script from the project root directory" -ForegroundColor Red
    exit 1
}

if ($Clean) {
    if (Test-Path "backend\\build") { rmdir /s /q backend\build }
    if (Test-Path "backend\\dist") { rmdir /s /q backend\dist }
}

# Build frontend
Push-Location frontend
try {
    if (-not (Test-Path "node_modules" -PathType Container)) {
        Write-Host "Installing frontend dependencies (pnpm install)..." -ForegroundColor Gray
        pnpm install
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency install failed" }
    }

    Write-Host "Building frontend (pnpm build)..." -ForegroundColor Gray
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
}
finally {
    Pop-Location
}

# Build backend desktop executable (GPU-capable)
Push-Location backend
try {
    Write-Host "Syncing Python dependencies (uv sync)..." -ForegroundColor Gray
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

    $spec = if ($OneFile) { "desktop_onefile.spec" } else { "desktop.spec" }
    Write-Host "Building desktop EXE with PyInstaller ($spec)..." -ForegroundColor Gray
    uv run pyinstaller $spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    if ($OneFile) {
        $out = Join-Path (Resolve-Path ".\").Path "dist\\Meeting Notes.exe"
    } else {
        $out = Join-Path (Resolve-Path ".\").Path "dist\\Meeting Notes\\Meeting Notes.exe"
    }
    Write-Host "\nBuild completed: $out" -ForegroundColor Green
}
finally {
    Pop-Location
}



