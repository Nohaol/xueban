$connection = Get-NetTCPConnection -LocalPort 18000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1

if (-not $connection) {
    Write-Host "XiaoZhi source server is not running on port 18000."
    exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
if (
    $process.Name -ne "python.exe" -or
    $process.ExecutablePath -notlike "*xiaozhi-server-sandbox*" -or
    $process.CommandLine -notlike "*app.py*"
) {
    throw "Port 18000 is owned by another process. Nothing was stopped."
}

Stop-Process -Id $connection.OwningProcess
Write-Host "XiaoZhi source server stopped."
