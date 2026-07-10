@echo off
REM run_checkin.bat - non-interactive wrapper for scripts/checkin.py, invoked
REM by Windows Task Scheduler at the 6h/12h/24h checkpoints. %1 is the label
REM (e.g. 6h). Appends console output to outputs\checkin\checkin_run.log so
REM a scheduled (non-interactive) run leaves a trace even if Task Scheduler's
REM own history is trimmed.
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0\.."

if "%~1"=="" (
    echo run_checkin.bat: missing label argument >> outputs\checkin\checkin_run.log
    exit /b 1
)

if not exist outputs\checkin mkdir outputs\checkin

echo. >> outputs\checkin\checkin_run.log
echo ==== %date% %time% : checkin label=%~1 ==== >> outputs\checkin\checkin_run.log
".venv\Scripts\python.exe" scripts\checkin.py --label %~1 >> outputs\checkin\checkin_run.log 2>&1
echo exit code %ERRORLEVEL% >> outputs\checkin\checkin_run.log
endlocal
