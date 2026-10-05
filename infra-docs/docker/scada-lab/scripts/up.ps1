$ErrorActionPreference = 'Stop'
docker compose up -d --build
Write-Host ''
Write-Host 'SCADA Lab iniciado:' -ForegroundColor Green
Write-Host 'Node-RED : http://localhost:1880'
Write-Host 'Dashboard: http://localhost:1880/dashboard'
Write-Host 'FUXA     : http://localhost:1881'
Write-Host 'MQTT     : localhost:1883'
Write-Host 'Modbus   : localhost:502'
Write-Host 'OPC-UA   : localhost:4840'
Write-Host 'S7       : localhost:1102'
