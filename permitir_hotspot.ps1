# Ejecutar este archivo desde PowerShell como administrador.
# Permite el acceso al dashboard por el hotspot de Windows solamente:
# PC hotspot: 192.168.137.1 | Puerto Flask: 8000 | Clientes: 192.168.137.0/24

$ErrorActionPreference = "Stop"
$ruleName = "MiniSumos RC Dashboard - Hotspot (TCP 8000)"

# Reemplaza la regla anterior del mismo nombre para mantenerla actualizada.
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Description "Permite MiniSumos RC desde dispositivos conectados al hotspot del PC." `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort 8000 `
    -LocalAddress 192.168.137.1 `
    -RemoteAddress 192.168.137.0/24 `
    -Profile Any

Write-Host ""
Write-Host "Regla creada para el hotspot." -ForegroundColor Green
Write-Host "Desde los dispositivos conectados al hotspot, abre:"
Write-Host "http://192.168.137.1:8000" -ForegroundColor Cyan
