# LifeLane SUMO Demo — One-Click Launcher (updated for Life_Lane_Demo)
param([switch]$NoCopy)

$ProjectDir = "C:\Users\hp\Desktop\Life_Lane_Demo"
$SumoHome   = "C:\Users\hp\Desktop\SUMO\sumo-win64-1.28.0"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   LifeLane — Emergency Preemption Demo  (v3.1)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# ── 1. Validate directories ───────────────────────────────────────────────────
if (-not (Test-Path $ProjectDir)) {
    Write-Host "[ERROR] Project not found at $ProjectDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}
if (-not (Test-Path $SumoHome)) {
    # Try SUMO_HOME env var
    if ($env:SUMO_HOME -and (Test-Path $env:SUMO_HOME)) {
        $SumoHome = $env:SUMO_HOME
    } else {
        Write-Host "[ERROR] SUMO not found. Expected: $SumoHome" -ForegroundColor Red
        Write-Host "        Set `$env:SUMO_HOME or install SUMO." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"; exit 1
    }
}
$env:SUMO_HOME = $SumoHome
Write-Host "[1/4] SUMO:    $SumoHome" -ForegroundColor Cyan
Write-Host "[1/4] Project: $ProjectDir" -ForegroundColor Cyan

# ── 2. Install Python packages ────────────────────────────────────────────────
Write-Host "[2/4] Checking Python packages..." -ForegroundColor Cyan
python -m pip install --quiet traci sumolib fastapi "uvicorn[standard]"
Write-Host "      Packages ready." -ForegroundColor Green

# ── 3. Generate SUMO network if missing ───────────────────────────────────────
$NetFile    = "$ProjectDir\sumo\lifelane.net.xml"
$Netconvert = "$SumoHome\bin\netconvert.exe"
if (-not (Test-Path $NetFile)) {
    Write-Host "[3/4] Generating road network..." -ForegroundColor Cyan
    python -c "
import subprocess, sys
r = subprocess.run([
    r'$Netconvert',
    '--node-files', r'$ProjectDir\sumo\lifelane.nod.xml',
    '--edge-files',  r'$ProjectDir\sumo\lifelane.edg.xml',
    '--output-file', r'$NetFile',
    '--tls.guess', 'true', '--tls.default-type', 'static', '--no-warnings'
], capture_output=True, text=True, cwd=r'$ProjectDir\sumo')
print(r.stdout or 'OK')
if r.returncode != 0:
    print('ERROR:', r.stderr[:300]); sys.exit(1)
"
    if (Test-Path $NetFile) {
        Write-Host "      lifelane.net.xml generated." -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Network generation failed." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
} else {
    Write-Host "[3/4] Network file exists, skipping generation." -ForegroundColor Green
}

# ── 4. Launch backend ─────────────────────────────────────────────────────────
Write-Host "[4/4] Launching backend..." -ForegroundColor Cyan
Write-Host ""
Write-Host "  Standalone Sim  -> http://localhost:8080/sim"  -ForegroundColor White
Write-Host "  SUMO Dashboard  -> http://localhost:8080/"     -ForegroundColor White
Write-Host "  API Docs        -> http://localhost:8080/docs" -ForegroundColor White
Write-Host ""
Write-Host "  To start SUMO simulation: POST http://localhost:8080/api/sumo/start" -ForegroundColor Yellow
Write-Host "  Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

Set-Location $ProjectDir

$backendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    python backend\server.py
} -ArgumentList $ProjectDir

Start-Sleep -Seconds 2
Start-Process "http://localhost:8080/sim"

Write-Host "Backend running. Streaming output:" -ForegroundColor Green
try {
    while ($true) {
        $out = Receive-Job $backendJob
        if ($out) { Write-Host $out }
        Start-Sleep -Milliseconds 500
        if ($backendJob.State -eq 'Failed' -or $backendJob.State -eq 'Completed') {
            Write-Host "[WARN] Backend process ended unexpectedly." -ForegroundColor Red
            break
        }
    }
} finally {
    Stop-Job    $backendJob -ErrorAction SilentlyContinue
    Remove-Job  $backendJob -ErrorAction SilentlyContinue
}
