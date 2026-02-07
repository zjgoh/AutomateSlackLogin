@echo off
title Install Python

echo Installing Python 3.12 via winget...
echo.

winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements

if errorlevel 1 (
    echo.
    echo Install failed. Install manually from https://www.python.org/downloads/
    echo Remember to check "Add Python to PATH" in the installer.
) else (
    echo.
    echo Python installed. Slack_Login will relaunch in a new window.
)

echo.
if /i not "%~1"=="auto" pause
