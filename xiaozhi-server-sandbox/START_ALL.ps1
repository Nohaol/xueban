$ErrorActionPreference = "Stop"

$sandbox = $PSScriptRoot
$statusLog = Join-Path $sandbox "startup-status.log"
$services = @(
    @{
        Name = "MQTT gateway"
        Ports = @(1883, 18007)
        Script = Join-Path $sandbox "START_MQTT_GATEWAY.ps1"
        Output = Join-Path $sandbox "runtime-mqtt.out.log"
        Error = Join-Path $sandbox "runtime-mqtt.err.log"
        Process = $null
        LastAttempt = [datetime]::MinValue
    },
    @{
        Name = "XiaoZhi source server"
        Ports = @(18000, 18003)
        Script = Join-Path $sandbox "START_SOURCE.ps1"
        Output = Join-Path $sandbox "runtime-server.out.log"
        Error = Join-Path $sandbox "runtime-server.err.log"
        Process = $null
        LastAttempt = [datetime]::MinValue
    },
    @{
        Name = "Parent console"
        Ports = @(8000)
        Script = Join-Path $sandbox "START_PARENT_ACTIVE.ps1"
        Output = Join-Path $sandbox "runtime-parent.out.log"
        Error = Join-Path $sandbox "runtime-parent.err.log"
        Process = $null
        LastAttempt = [datetime]::MinValue
    }
)

function Test-Port([int]$port) {
    return $null -ne (
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    )
}

function Test-ServiceReady([hashtable]$service) {
    return @(
        $service.Ports | Where-Object { -not (Test-Port $_) }
    ).Count -eq 0
}

function Write-StartupStatus([string]$message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $message
    Add-Content -LiteralPath $statusLog -Value $line -Encoding UTF8
}

function Start-ServiceProcess([hashtable]$service) {
    $service.LastAttempt = Get-Date
    $service.Process = Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $service.Script
        ) `
        -WindowStyle Hidden `
        -RedirectStandardOutput $service.Output `
        -RedirectStandardError $service.Error `
        -PassThru
    Write-StartupStatus (
        "Starting {0}, PID {1}, ports {2}" -f
        $service.Name,
        $service.Process.Id,
        ($service.Ports -join ",")
    )
}

Write-StartupStatus "Startup check began."
$deadline = (Get-Date).AddMinutes(3)
do {
    foreach ($service in $services) {
        if (Test-ServiceReady $service) {
            continue
        }

        $running = (
            $null -ne $service.Process -and
            -not $service.Process.HasExited
        )
        $retryDue = (
            ((Get-Date) - $service.LastAttempt).TotalSeconds -ge 5
        )
        if (-not $running -and $retryDue) {
            Start-ServiceProcess $service
        }
    }

    $missingPorts = @(
        $services.Ports |
            ForEach-Object { $_ } |
            Where-Object { -not (Test-Port $_) }
    )
    if ($missingPorts.Count -eq 0) {
        Write-StartupStatus "All local services are ready."
        exit 0
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

Write-StartupStatus "Startup failed. Missing ports: $($missingPorts -join ', ')"
throw "Local services did not become ready. Missing ports: $($missingPorts -join ', ')"
