# Generate SUMO road network (run from the sumo/ folder)
$sumoHome = $env:SUMO_HOME
if (-not $sumoHome -or -not (Test-Path $sumoHome)) {
    $sumoHome = "C:\Users\hp\Desktop\SUMO\sumo-win64-1.28.0"
}
$netconvert = Join-Path $sumoHome "bin\netconvert.exe"
Write-Host "Using netconvert: $netconvert"
Push-Location $PSScriptRoot
& $netconvert `
    --node-files lifelane.nod.xml `
    --edge-files lifelane.edg.xml `
    --output-file lifelane.net.xml `
    --tls.guess true `
    --tls.default-type static `
    --no-warnings
Pop-Location
Write-Host "Done -> lifelane.net.xml"
