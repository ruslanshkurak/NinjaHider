@echo off
title NinjaHider Console
cd /d "%~dp0"

echo Starting background hidden process...
taskkill /F /IM pythonw.exe >nul 2>&1
start "" pythonw winhider.py --daemon

echo Starting Control Panel...
python winhider.py
pause
