$ErrorActionPreference = 'Stop'
docker compose ps
Write-Host "`nMQTT test" -ForegroundColor Cyan
docker compose exec mosquitto mosquitto_pub -h localhost -t lab/plant/level -m 65.5
Write-Host "`nSimulator logs" -ForegroundColor Cyan
docker compose logs --tail=20 modbus-sim opcua-sim s7-sim
