@echo off
chcp 65001 >nul
title 發票記帳
cd /d "%~dp0"

rem 本機 AI 模型。電腦沒有獨立顯示卡、跑得很慢的話，改成 qwen2.5vl:3b
if not defined OLLAMA_MODEL set "OLLAMA_MODEL=qwen2.5vl:7b"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo   找不到 Python。請到 https://www.python.org/downloads/ 下載安裝，
  echo   安裝時記得勾選「Add python.exe to PATH」，裝好後再雙擊這個檔案。
  echo.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 第一次啟動，正在準備環境（約 1 到 3 分鐘）...
  %PY% -m venv .venv || goto fail
)

fc /b requirements.txt .venv\installed-requirements.txt >nul 2>nul
if errorlevel 1 (
  echo 正在安裝需要的套件...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto fail
  copy /y requirements.txt .venv\installed-requirements.txt >nul
)

".venv\Scripts\python.exe" run.py
pause
exit /b 0

:fail
echo.
echo   安裝失敗，請把上面的錯誤訊息截圖給 Cursor 看。
pause
exit /b 1
