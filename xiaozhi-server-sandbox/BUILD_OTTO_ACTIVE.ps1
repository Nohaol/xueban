$ErrorActionPreference = "Stop"

$env:IDF_GITHUB_ASSETS = "dl.espressif.com/github_assets"
$idf = "D:\esp-idf-v5.5.4"
$workspace = Split-Path -Parent $PSScriptRoot
$project = "D:\xueban-esp32-buildsrc"
$gitPath = Join-Path $workspace "github-tools\mingit\cmd"
$env:PATH = "$gitPath;$env:PATH"

. "$idf\export.ps1"
Set-Location -LiteralPath $project

$configured = (
    (Test-Path -LiteralPath (Join-Path $project "build\build.ninja")) -and
    (Select-String -LiteralPath (Join-Path $project "sdkconfig") `
        -Pattern "^CONFIG_BOARD_TYPE_OTTO_ROBOT=y$" -Quiet)
)

if ($configured) {
    ninja -C build -j 1
    if ($LASTEXITCODE -ne 0) {
        throw "Single-thread firmware build failed."
    }
    python -c "from scripts.release import get_project_version, merge_bin, zip_bin; merge_bin(); zip_bin('otto-robot-local-active', get_project_version())"
    if ($LASTEXITCODE -ne 0) {
        throw "Firmware packaging failed."
    }
} else {
    python scripts\release.py otto-robot `
        --config config.local-active.json `
        --name otto-robot-local-active
    if ($LASTEXITCODE -ne 0) {
        throw "Firmware build failed."
    }
}

$release = Join-Path $project "releases\v2.2.6_otto-robot-local-active.zip"
if (-not (Test-Path -LiteralPath $release)) {
    throw "Expected firmware package was not created."
}
Copy-Item -LiteralPath $release `
    -Destination (Join-Path $workspace "xiaozhi-esp32\releases") `
    -Force
