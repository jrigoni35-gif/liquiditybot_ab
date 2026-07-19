@echo off
REM start.bat - ONE command to run the bot.
REM The bot runs in its own window. Use stop.bat to stop it.
REM Observability lives in Grafana Cloud (see docs/PHONE_SESSIONS.md);
REM control is the git remote-control plane (scripts/remote_control.py).
REM
REM For a hands-off, WINDOWLESS always-on run, prefer install_autostart.bat
REM (hidden supervisor at logon, no console). This script is the manual path.
setlocal
REM quoted form: bare `set PYTHONUTF8=1 && ...` captures the space before && into
REM the value ("1 "), which Python 3.14 rejects as an invalid PYTHONUTF8 value
REM (fatal at preinit). Quotes delimit the value exactly.
set "PYTHONUTF8=1"
cd /d "%~dp0"

if not exist .venv\Scripts\activate.bat (
    echo No .venv found - running install.bat first...
    call install.bat || exit /b 1
)
call .venv\Scripts\activate.bat

REM Already running? Do NOT open another window. A fresh heartbeat in
REM outputs\status.json means a bot (hidden supervisor OR an existing window)
REM already holds the SingleInstanceLock; a second start.bat would only leave a
REM dead `cmd /k` shell behind - the stacked-window cascade. Report here, exit.
python "%~dp0scripts\bot_alive.py"
if not errorlevel 1 (
    echo Bot already running - fresh heartbeat in outputs\status.json.
    echo Not opening another window. Use stop.bat to stop it, or
    echo scripts\tidy_windows.bat to clear any stray windows already open.
    goto :done
)

echo Starting bot (its own window)...
REM The runner's SingleInstanceLock refuses a duplicate bot, so a second
REM start.bat cannot double-run the engine - the extra window just exits.
start "liquiditybot-runner" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && set "PYTHONUTF8=1" && python runner.py"

:done
endlocal
