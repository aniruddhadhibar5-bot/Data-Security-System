@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON=py"
) else (
    set "PYTHON=python"
)

echo Installing Data Security System dependencies...
%PYTHON% -m pip install --user -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check your internet connection and Python installation.
    pause
    exit /b 1
)

echo Starting Data Security System...
%PYTHON% "%~dp0main.py"
if errorlevel 1 (
    echo.
    echo The application stopped with an error.
    pause
)
endlocal
