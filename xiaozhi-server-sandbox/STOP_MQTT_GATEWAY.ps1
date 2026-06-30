$connection = Get-NetTCPConnection -LocalPort 1883 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1

if (-not $connection) {
    Write-Host "MQTT gateway is not running on port 1883."
    exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
if (
    $process.Name -ne "node.exe" -or
    $process.ExecutablePath -notlike "*xiaozhi-server-sandbox*" -or
    $process.CommandLine -notlike "*app.js*"
) {
    throw "Port 1883 is owned by another process. Nothing was stopped."
}

Stop-Process -Id $connection.OwningProcess
Write-Host "MQTT gateway stopped."
