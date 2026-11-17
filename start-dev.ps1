<#
.SYNOPSIS
    LifeLane development launcher -- starts backend and frontend together.
.DESCRIPTION
    Launches the FastAPI backend on port 8000 and the Vite frontend on port 5173
    in separate windows. Press Ctrl+C in each window to stop.
.USAGE
    From the project root (C:\Users\hp\Desktop\LifeLane\LifeLane):
        .\start-dev.ps1
#>

$Root = $PSScriptRoot

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  LifeLane Dev Launcher" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# -- Activate venv and start backend ------------------------------------------
Write-Host "[1/2] Starting backend on http://localhost:8000 ..." -ForegroundColor Cyan
$backendCmd = "cd '$Root'; `$env:PYTHONPATH = 'src'; & '.venv\Scripts\python.exe' -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal

# Give the backend a moment to bind
Start-Sleep -Seconds 3

# -- Start frontend ------------------------------------------------------------
Write-Host "[2/2] Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
$frontendCmd = "cd '$Root\frontend'; pnpm dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal

Write-Host ""
Write-Host "--------------------------------------------" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "--------------------------------------------" -ForegroundColor Green
Write-Host ""
Write-Host "Both servers are running in separate windows." -ForegroundColor Yellow
Write-Host "Close those windows (or Ctrl+C in each) to stop." -ForegroundColor Yellow
Write-Host ""
