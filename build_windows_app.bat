@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

if not exist "xxxx.py" exit /b 1
if not exist "mars_app.py" exit /b 1
if not exist "题库.xlsx" exit /b 1

py -3.12 -m venv .windows-app-venv
if errorlevel 1 exit /b 1
".windows-app-venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt "pyinstaller>=6.10,<7"
if errorlevel 1 exit /b 1
".windows-app-venv\Scripts\python.exe" build_desktop.py
if errorlevel 1 exit /b 1

echo Built and tested: %CD%\dist\desktop
exit /b 0
