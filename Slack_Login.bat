@echo off
:: All paths are relative to this file's folder (project root). Run everything from here.
cd /d "%~dp0"
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "VENV_PIP=%ROOT%.venv\Scripts\pip.exe"
set "REQUIREMENTS=%ROOT%library\requirements.txt"
set "SCRIPT=%ROOT%library\slack_auto_login.py"
set "PY="

:: ---- Use isolated project venv if it exists ----
if exist "%VENV_PY%" (
    echo Using isolated environment: .venv
    goto :use_venv
)

:: ---- No venv yet: find system Python to create one ----
python --version >nul 2>&1
if not errorlevel 1 set "PY=python" & goto :create_venv
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3" & goto :create_venv
py --version >nul 2>&1
if not errorlevel 1 set "PY=py" & goto :create_venv
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe" & goto :create_venv
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe" & goto :create_venv
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe" & goto :create_venv
if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe" & goto :create_venv
if exist "%ProgramFiles%\Python311\python.exe" set "PY=%ProgramFiles%\Python311\python.exe" & goto :create_venv
if exist "%ProgramFiles%\Python313\python.exe" set "PY=%ProgramFiles%\Python313\python.exe" & goto :create_venv
goto :nopython

:create_venv
echo [1/4] Creating isolated environment in .venv ...
%PY% -m venv "%ROOT%.venv"
if errorlevel 1 (
    echo      venv creation failed.
    goto :end
)
echo      Done. Installing dependencies into .venv ...
"%VENV_PIP%" install --upgrade pip >nul 2>&1
"%VENV_PIP%" install -r "%REQUIREMENTS%"
if errorlevel 1 (
    echo      pip install failed.
    goto :end
)
echo.
echo [2/4] Starting Slack auto-login...
goto :run

:use_venv
:: If venv exists but deps missing, install
"%VENV_PY%" -c "import selenium, webdriver_manager, dotenv" >nul 2>&1
if not errorlevel 1 (
    echo [1/2] Dependencies already installed in .venv. Starting Slack auto-login...
    goto :run
)
echo [1/3] Installing/updating dependencies in .venv ...
"%VENV_PIP%" install --upgrade pip >nul 2>&1
"%VENV_PIP%" install -r "%REQUIREMENTS%"
if errorlevel 1 (
    echo      pip install failed.
    goto :end
)
echo [2/3] Starting Slack auto-login...

:run
echo.
"%VENV_PY%" "%SCRIPT%"
echo.
echo Done.
goto :end

:nopython
echo Python is not installed or not in PATH.
echo.
echo Running Install Python (step by step)...
echo.
call "%ROOT%library\Install_Python.bat" auto
echo.
echo Relaunching Slack Login in a new window...
start "Slack Login" cmd /k "cd /d "%~dp0" && "%~f0""
exit /b 0

:end
echo.
echo Closing in 2 seconds...
timeout /t 2 /nobreak >nul
exit
