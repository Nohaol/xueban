@echo off
chcp 65001 >nul
title 小智伴学服务启动
echo 正在启动家长端、主动播报和小智本地服务，请稍候...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0xiaozhi-server-sandbox\START_ALL.ps1"
if errorlevel 1 (
  echo.
  echo 启动失败，请查看 xiaozhi-server-sandbox\startup-status.log
  pause
  exit /b 1
)
echo 五个服务已经全部启动。
start "" "http://127.0.0.1:8000/local-agent"
