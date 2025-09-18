# Development script for Meeting Notes Desktop Application
# Runs the desktop app directly without building

Write-Host "Meeting Notes Desktop Development Mode" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# Check if we're in the right directory
if (-not (Test-Path "backend" -PathType Container)) {
    Write-Host "Error: Please run this script from the project root directory" -ForegroundColor Red
    exit 1
}

# Check if frontend is built
if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Frontend not built. Building now..." -ForegroundColor Yellow
    Push-Location frontend
    
    # Install dependencies if needed
    if (-not (Test-Path "node_modules" -PathType Container)) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Gray
        pnpm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to install frontend dependencies" -ForegroundColor Red
            Pop-Location
            exit 1
        }
    }
    
    # Build frontend
    Write-Host "Building frontend..." -ForegroundColor Gray
    pnpm build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to build frontend" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "Frontend built successfully!" -ForegroundColor Green
}

# Run the desktop app
Write-Host "`nStarting Meeting Notes Desktop..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray

Push-Location backend
try {
    uv run python -m app.desktop
} finally {
    Pop-Location
}
