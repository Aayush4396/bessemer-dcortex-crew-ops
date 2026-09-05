# ==============================================================================
# start.ps1 -- dCortex Crew Operations Advisor Startup Script for PowerShell
# Starts both FastAPI Backend (Port 8000) and React Vite Frontend (Port 5173).
# Compatible with Windows PowerShell 5.1 and PowerShell Core 7+.
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   dCortex Crew Operations Advisor (NOC AI Copilot)             " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

# 1. Virtual Environment & Python Check
Write-Host "[1/4] Checking Python virtual environment..." -ForegroundColor Yellow
$PythonExe = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Virtual environment not found. Creating .venv..." -ForegroundColor Yellow
    python -m venv .venv
    & $PythonExe -m pip install -r requirements.txt
}
Write-Host "[OK] Using Python at: $PythonExe" -ForegroundColor Green

# 2. Configuration & SQLite Database Check
Write-Host "[2/4] Verifying configuration and database..." -ForegroundColor Yellow
$EnvFile = Join-Path $RootDir ".env"
$EnvExample = Join-Path $RootDir ".env.example"

if ((-not (Test-Path $EnvFile)) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "[!] Created .env from .env.example. Please ensure SARVAM_API_KEY is configured." -ForegroundColor Yellow
}

$DbFile = Join-Path $RootDir "crew_ops.db"
if (-not (Test-Path $DbFile)) {
    Write-Host "Database not found. Initializing SQLite database (crew_ops.db)..." -ForegroundColor Yellow
    & $PythonExe -m src.db.loader
    Write-Host "[OK] Database initialized successfully." -ForegroundColor Green
}
else {
    Write-Host "[OK] SQLite database detected (crew_ops.db)." -ForegroundColor Green
}

# 3. Start Backend & Frontend Jobs
Write-Host "[3/4] Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$BackendJob = Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn src.api.server:app --host 127.0.0.1 --port 8000" -PassThru -NoNewWindow

Start-Sleep -Seconds 2

Write-Host "[4/4] Starting React frontend on http://127.0.0.1:5173..." -ForegroundColor Yellow
$FrontendDir = Join-Path $RootDir "frontend"
$NodeModules = Join-Path $FrontendDir "node_modules"

if (-not (Test-Path $NodeModules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location $FrontendDir
    npm install
    Set-Location $RootDir
}

$FrontendJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory $FrontendDir -PassThru -NoNewWindow

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "   dCortex NOC AI Copilot is LIVE!                              " -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "   * Frontend Console : http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "   * Backend API      : http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "   * Swagger Docs     : http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor White
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host ""
    Write-Host "Stopping dCortex services..." -ForegroundColor Yellow
    if ($BackendJob -and -not $BackendJob.HasExited) {
        Stop-Process -Id $BackendJob.Id -Force -ErrorAction SilentlyContinue
    }
    if ($FrontendJob -and -not $FrontendJob.HasExited) {
        Stop-Process -Id $FrontendJob.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "All processes stopped cleanly." -ForegroundColor Green
}
