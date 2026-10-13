@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Setup.bat first. See WINDOWS_GUIDE.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo MicBoost could not run. Check the error above.
    pause
    exit /b 1
)
