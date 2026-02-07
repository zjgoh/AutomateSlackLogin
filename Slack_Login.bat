@echo off
cd /d "%~dp0"
set "PY="

:: Find Python: try 'python', then 'py -3', then 'py', then common install paths
python --version >nul 2>&1
if not errorlevel 1 set "PY=python" & goto :found
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3" & goto :found
py --version >nul 2>&1
if not errorlevel 1 set "PY=py" & goto :found
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe" & goto :found
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe" & goto :found
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe" & goto :found
if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe" & goto :found
if exist "%ProgramFiles%\Python311\python.exe" set "PY=%ProgramFiles%\Python311\python.exe" & goto :found
if exist "%ProgramFiles%\Python313\python.exe" set "PY=%ProgramFiles%\Python313\python.exe" & goto :found
goto :nopython

:found
echo [1/4] Checking for latest pip...
%PY% -m pip install --upgrade pip
if errorlevel 1 echo      pip upgrade failed (non-fatal, continuing).
echo.

echo [2/4] Installing/updating dependencies...
%PY% -m pip install -r "%~dp0library\requirements.txt"
if errorlevel 1 (
    echo      pip install failed.
    goto :end
)

echo.
echo [3/4] Starting Slack auto-login...
echo.
%PY% "%~dp0library\slack_auto_login.py"
echo.
echo [4/4] Done.
goto :end

:nopython
echo Python is not installed or not in PATH.
echo.
echo Running Install Python (step by step)...
echo.
call "%~dp0library\Install_Python.bat" auto
echo.
echo Relaunching Slack Login in a new window...
start "Slack Login" cmd /k "cd /d "%~dp0" && "%~f0""
exit /b 0

:end
pause
