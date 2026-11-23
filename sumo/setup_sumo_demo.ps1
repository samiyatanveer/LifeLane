# LifeLane SUMO Demo Setup Script
# Run this once to generate the network file

$sumoHome = $env:SUMO_HOME
if (-not $sumoHome) { $sumoHome = "C:\Users\hp\Desktop\SUMO\sumo-win64-1.28.0" }
$netconvert = Join-Path $sumoHome "bin\netconvert.exe"

Write-Host "[1/3] Installing Python TraCI packages..."
& python -m pip install traci sumolib

Write-Host "[2/3] Generating SUMO network..."
Push-Location $PSScriptRoot
& $netconvert --node-files lifelane.nod.xml --edge-files lifelane.edg.xml --output-file lifelane.net.xml --tls.guess true --tls.default-type static --no-warnings
Pop-Location
Write-Host "      => lifelane.net.xml created"

Write-Host "[3/3] Done! You can now click 'Start Simulation' in the LifeLane frontend."
Write-Host "      Or run manually: python sumo\traci_controller.py"
