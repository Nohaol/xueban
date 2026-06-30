$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $PSScriptRoot
$python = "C:\Users\86153\anaconda3\python.exe"
$env:XIAOZHI_ACTIVE_SPEECH_URL = "http://127.0.0.1:18007/study-alert"
$env:XIAOZHI_ACTIVE_SPEECH_DEVICE_ID = "90:70:69:0e:a4:ac"
$env:XIAOZHI_ACTIVE_SPEECH_TIMEOUT = "2"

Set-Location -LiteralPath $workspace
& $python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
