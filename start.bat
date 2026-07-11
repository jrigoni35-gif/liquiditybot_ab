@echo off
REM start.bat - ONE command to run everything: bot + dashboard.
REM The bot runs in its own window; the dashboard opens in your browser.
REM Close the dashboard anytime - the bot keeps running. Use stop.bat to stop it.
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

echo Starting bot (its own window)...
REM The runner's SingleInstanceLock refuses a duplicate bot, so a second
REM start.bat cannot double-run the engine - the extra window just exits.
start "liquiditybot-runner" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && set "PYTHONUTF8=1" && python runner.py"

REM Duplicate-dashboard guard: a second start.bat used to spawn a second
REM streamlit on another port, leaving two operator consoles fighting over
REM the same bot (root cause of the 2026-07 stray-stop incident). If the
REM dashboard port is already listening, open the existing one instead.
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul 2>nul
if %errorlevel% equ 0 (
    echo Dashboard already running - opening it instead of starting a second one.
    start http://127.0.0.1:8501
    goto :done
)

echo Starting dashboard (browser opens automatically)...
echo   Ctrl+C here closes the dashboard only; the bot keeps running.
echo   Run stop.bat to stop the bot.
REM --server.address is belt-and-braces with .streamlit\config.toml: the
REM operator dashboard (stop/flatten/ARM controls) must never listen on
REM anything but loopback.
python -m streamlit run ui\dashboard.py --server.address=127.0.0.1 --server.port=8501

:done
endlocal
