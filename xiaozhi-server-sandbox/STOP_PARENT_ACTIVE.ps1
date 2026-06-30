$connection = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1

if (-not $connection) {
    Write-Host "Parent console is not running on port 8000."
    exit 0
}

$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
if (
    $process.Name -ne "python.exe" -or
    $process.CommandLine -notlike "*uvicorn backend.main:app*"
) {
    throw "Port 8000 is owned by another process. Nothing was stopped."
}

Stop-Process -Id $connection.OwningProcess
Write-Host "Parent console stopped."
