@echo off
setlocal
set SCRIPT_DIR=%~dp0
set OUT_DIR=%SCRIPT_DIR%reports
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set D=%%c%%a%%b
for /f "tokens=1-2 delims=:." %%a in ("%time%") do set T=%%a%%b
set T=%T: =0%
set OUT=%OUT_DIR%\hw-health-%COMPUTERNAME%-%D%-%T%.json

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Get-HardwareHealth.ps1" -OutputJson "%OUT%" -HostMonitorLogHours 24
echo Output=%OUT%
exit /b %ERRORLEVEL%
