@echo off
setlocal
cd /d "%~dp0"
echo Preparing MicBoost. Internet connection is required.
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_error
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Double-click Start.bat to launch.
pause
exit /b 0
:python_error
echo Install Python 3.11 or newer from python.org, including the Python launcher.
echo See WINDOWS_GUIDE.md for instructions.
pause
exit /b 1
:failed
echo Setup failed. Keep this window open and check the error above.
pause
exit /b 1
