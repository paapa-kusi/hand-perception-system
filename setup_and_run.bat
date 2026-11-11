@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 goto no_python

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project Python environment...
    py -3 -m venv .venv
    if errorlevel 1 goto setup_failed
)

echo Installing or checking the small application dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto setup_failed

echo Starting hand perception. The two CV models download automatically on first run.
".venv\Scripts\python.exe" launch.py %*
exit /b %errorlevel%

:no_python
echo Python 3 is required. Install Python 3.11 or newer from https://www.python.org/downloads/ and enable the Python Launcher, then run this file again.
pause
exit /b 1

:setup_failed
echo Setup or startup failed. Check the message above and your internet connection.
pause
exit /b 1

