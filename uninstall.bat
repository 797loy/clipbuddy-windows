@echo off
cd /d "%~dp0"
python scripts\setup.py uninstall
echo Your history is kept in %%APPDATA%%\ClipBuddy (delete the folder to remove it).
pause
