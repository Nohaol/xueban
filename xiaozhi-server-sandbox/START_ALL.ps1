$ErrorActionPreference = "Stop"

$sandbox = $PSScriptRoot
$services = @(
    @{
        Name = "MQTT gateway"
        Ports = @(1883, 18007)
        Script = Join-Path $sandbox "START_MQTT_GATEWAY.ps1"
        Output = Join-Path $sandbox "runtime-mqtt.out.log"
        Error = Join-Path $sandbox "runtime-mqtt.err.log"
    },
    @{
        Name = "XiaoZhi source server"
        Ports = @(18000, 18003)
        Script = Join-Path $sandbox "START_SOURCE.ps1"
        Output = Join-Path $sandbox "runtime-server.out.log"
        Error = Join-Path $sandbox "runtime-server.err.log"
    },
    @{
        Name = "Parent console"
        Ports = @(8000)
        Script = Join-Path $sandbox "START_PARENT_ACTIVE.ps1"
        Output = Join-Path $sandbox "runtime-parent.out.log"
        Error = Join-Path $sandbox "runtime-parent.err.log"
    }
)

function Test-Port([int]$port) {
    return $null -ne (
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
}

foreach ($service in $services) {
    $ready = @($service.Ports | Where-Object { -not (Test-Port $_) }).Count -eq 0
    if ($ready) {
        continue
    }

    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $service.Script
        ) `
        -WindowStyle Hidden `
        -RedirectStandardOutput $service.Output `
        -RedirectStandardError $service.Error
}

$deadline = (Get-Date).AddSeconds(120)
do {
    $missingPorts = @(
        $services.Ports |
            ForEach-Object { $_ } |
            Where-Object { -not (Test-Port $_) }
    )
    if ($missingPorts.Count -eq 0) {
        exit 0
    }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)

throw "Local services did not become ready. Missing ports: $($missingPorts -join ', ')"
