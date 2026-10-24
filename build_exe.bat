@echo off
cd /d "%~dp0"
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --noconsole --name ClipBuddy --icon assets\icon.ico ^
  --add-data "ui;ui" --add-data "assets;assets" --collect-all webview app.py
echo Output: dist\ClipBuddy\ClipBuddy.exe
pause
