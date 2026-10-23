@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\發票記帳.lnk');" ^
  "$s.TargetPath = '%~dp0start.bat'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()"
if errorlevel 1 (
  echo 設定失敗。
) else (
  echo 完成！以後開機會自動啟動發票記帳（視窗會縮小在工作列）。
  echo 想取消的話，雙擊 autostart-off.bat。
)
pause
