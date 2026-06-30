$ErrorActionPreference = "Stop"

$shell = New-Object -ComObject WScript.Shell
$startup = $shell.SpecialFolders("Startup")
$shortcutPath = Join-Path $startup "Xueban Local Services.lnk"
$startAll = Join-Path $PSScriptRoot "START_ALL.ps1"

$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Get-Command powershell.exe).Source
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startAll`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Description = "Start XiaoZhi study companion services"
$shortcut.Save()

Write-Output $shortcutPath
