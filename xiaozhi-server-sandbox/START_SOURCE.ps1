$ErrorActionPreference = "Stop"

$sandbox = $PSScriptRoot
$workspace = Split-Path -Parent $sandbox
$server = Join-Path $sandbox "source-complete\xiaozhi-esp32-server-main\main\xiaozhi-server"
$template = Join-Path $sandbox "source-server.config.template.yaml"
$knowledgePath = Get-ChildItem -LiteralPath (Join-Path $workspace "knowledge_base") -Filter "*.md" |
    Sort-Object Length |
    Select-Object -First 1 -ExpandProperty FullName
$existingEnv = Join-Path $workspace "miniprogram-1\.env"
$environmentRoot = "C:\Users\86153\anaconda3\envs\xiaozhi-server-sandbox"
$python = Join-Path $environmentRoot "python.exe"
$env:PATH = "$environmentRoot;$environmentRoot\Library\bin;$environmentRoot\Scripts;$env:PATH"

function Read-DotEnvValue([string]$name) {
    $line = Get-Content -LiteralPath $existingEnv |
        Where-Object { $_ -match "^\s*$([regex]::Escape($name))\s*=" } |
        Select-Object -First 1
    if (-not $line) {
        throw "Missing $name in the existing parent-console .env file."
    }
    return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

$apiKey = Read-DotEnvValue "DEEPSEEK_API_KEY"
$baseUrl = Read-DotEnvValue "DEEPSEEK_BASE_URL"
$model = Read-DotEnvValue "DEEPSEEK_MODEL"
$mqttSignatureKey = $env:MQTT_SIGNATURE_KEY
if (-not $mqttSignatureKey) {
    throw "Missing MQTT_SIGNATURE_KEY environment variable."
}
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

$config = Get-Content -Raw -Encoding UTF8 -LiteralPath $template
$knowledge = Get-Content -Raw -Encoding UTF8 -LiteralPath $knowledgePath
$knowledgeBlock = (($knowledge -split "\r?\n") | ForEach-Object { "  $_" }) -join "`n"
$config = $config.Replace("__LOCAL_IP__", $localIp)
$config = $config.Replace("__DEEPSEEK_API_KEY__", $apiKey)
$config = $config.Replace("__DEEPSEEK_BASE_URL__", $baseUrl)
$config = $config.Replace("__DEEPSEEK_MODEL__", $model)
$config = $config.Replace("__MQTT_SIGNATURE_KEY__", $mqttSignatureKey)
$config = $config.Replace("__LOCAL_KNOWLEDGE__", $knowledgeBlock)

$dataDir = Join-Path $server "data"
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
[IO.File]::WriteAllText(
    (Join-Path $dataDir ".config.yaml"),
    $config,
    [Text.UTF8Encoding]::new($false)
)

Set-Location -LiteralPath $server
& $python "app.py"
