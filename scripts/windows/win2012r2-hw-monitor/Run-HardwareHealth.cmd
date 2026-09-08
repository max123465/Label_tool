@echo off
REM 台積電內網建議流程：先 Diagnose，再正式收集
setlocal
set SCRIPT_DIR=%~dp0
set OUT_DIR=%SCRIPT_DIR%reports
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

echo ===== Step 1/2 Diagnose =====
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Diagnose-Prerequisites.ps1"
echo.
echo ===== Step 2/2 Collect =====

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set D=%%c%%a%%b
for /f "tokens=1-2 delims=:." %%a in ("%time%") do set T=%%a%%b
set T=%T: =0%
set OUT=%OUT_DIR%\hw-health-%COMPUTERNAME%-%D%-%T%.json

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Get-HardwareHealth.ps1" -OutputJson "%OUT%" -HostMonitorLogHours 24
set RC=%ERRORLEVEL%
echo.
echo ExitCode=%RC%  (0=OK, 1=WARN, 2=BAD)
echo Output=%OUT%
exit /b %RC%
