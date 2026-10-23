@echo off
chcp 65001 >nul
powershell -NoProfile -Command "Remove-Item -ErrorAction SilentlyContinue ([Environment]::GetFolderPath('Startup') + '\發票記帳.lnk')"
echo 已取消開機自動啟動。
pause
