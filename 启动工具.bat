@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto nopython

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto oldpython

python app.py
if errorlevel 1 pause
exit /b 0

:nopython
echo.
echo Python 3.11+ was not found.
echo Install Python and enable "Add Python to PATH", then try again.
echo.
pause
exit /b 1

:oldpython
echo.
echo Python is too old. Python 3.11 or newer is required.
echo.
pause
exit /b 1
