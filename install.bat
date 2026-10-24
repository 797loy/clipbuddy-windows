@echo off
cd /d "%~dp0"
echo [1/2] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies. Please check that Python 3.9-3.13 is installed and on PATH.
  pause
  exit /b 1
)
echo [2/2] Creating desktop shortcut and autostart entry...
python scripts\setup.py install
echo.
echo Done. Double-click "ClipBuddy" on your desktop, or press Ctrl+Shift+V / F8 after launching.
pause
