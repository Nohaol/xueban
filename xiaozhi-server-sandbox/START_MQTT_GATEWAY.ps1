$ErrorActionPreference = "Stop"

$sandbox = $PSScriptRoot
$gateway = Join-Path $sandbox "mqtt-gateway-source\xiaozhi-mqtt-gateway-main"
$node = Join-Path $sandbox "tools\node-v22.23.1-win-x64\node.exe"
$localIp = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254*" -and
        $_.InterfaceAlias -eq "WLAN"
    } |
    Select-Object -First 1 -ExpandProperty IPAddress
if (-not $localIp) {
    throw "No active WLAN IPv4 address was found."
}
$env:PUBLIC_IP = $localIp

Set-Location -LiteralPath $gateway
& $node "app.js"
