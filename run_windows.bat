@echo off
cd /d "%~dp0"
title StudentIQ Full Stack
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  py -m venv .venv
  if errorlevel 1 (
    echo Python 3 was not found. Install Python from https://www.python.org/downloads/
    echo During installation tick "Add Python to PATH".
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (echo Dependency installation failed. Check your internet connection.&pause&exit /b 1)
)
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
pause
