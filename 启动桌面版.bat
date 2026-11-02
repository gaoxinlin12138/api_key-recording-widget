@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto nobuild
".venv\Scripts\python.exe" -c "import webview" >nul 2>nul
if errorlevel 1 goto nodig

".venv\Scripts\python.exe" app.py --native
if errorlevel 1 pause
exit /b 0

:nobuild
echo.
echo Desktop mode needs the build environment.
echo Run build_exe.bat once, then try this file again.
echo.
pause
exit /b 1

:nodig
echo.
echo pywebview is not installed in .venv.
echo Run build_exe.bat once, then try this file again.
echo.
pause
exit /b 1
