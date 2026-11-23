# Run from the LifeLane\sumo directory
$sumoPath = "C:\Users\hp\Desktop\SUMO\sumo-win64-1.28.0\bin"
& "$sumoPath\netconvert.exe" --node-files lifelane.nod.xml --edge-files lifelane.edg.xml --output-file lifelane.net.xml --tls.guess true --tls.default-type static
Write-Host "Network generated: lifelane.net.xml"
