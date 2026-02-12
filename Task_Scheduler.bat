@echo off
setlocal EnableDelayedExpansion

:: Force working directory to this script folder
cd /d "%~dp0"

echo =====================================
echo Slack Auto Runner
echo =====================================

set "FLAGFILE=ran_today.flag"
set "TARGET=Slack_Login.bat"

:: Get stable date (yyyyMMdd)
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set TODAY=%%i

:: Get current time
for /f "tokens=1-2 delims=:" %%a in ("%time%") do (
    set HH=%%a
    set MM=%%b
)

set HH=!HH: =!

:: Convert to minutes
set /a currentMinutes=HH*60+MM
set /a startMinutes=8*60+30
set /a endMinutes=9*60+30

echo Current Time: !HH!:!MM!
echo Checking window (08:30 - 09:30)...
echo.

:: Create flag file if missing
if not exist "%FLAGFILE%" (
    echo Creating flag file...
    >"%FLAGFILE%" echo 00000000
)

:: Read last run date
set /p LASTRUN=<"%FLAGFILE%"

:: If already ran today → exit
if "!LASTRUN!"=="!TODAY!" (
    echo Task already ran today.
    goto :end
)

:: Check time window
if !currentMinutes! GEQ !startMinutes! if !currentMinutes! LEQ !endMinutes! (

    echo Within allowed time.
    echo Setting flag for today...
    
    :: WRITE FLAG FIRST (critical fix)
    >"%FLAGFILE%" echo !TODAY!

    echo Running Slack_Login...
    
    :: Run in separate cmd so it cannot kill parent
    cmd /c "%TARGET%"

    echo Done.

) else (
    echo Not within time window to run this task.
)

:end
echo.
echo Closing in 0 seconds...
timeout /t 0 >nul
endlocal
exit