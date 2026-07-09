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
start "liquiditybot-runner" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && set "PYTHONUTF8=1" && python runner.py"

echo Starting dashboard (browser opens automatically)...
echo   Ctrl+C here closes the dashboard only; the bot keeps running.
echo   Run stop.bat to stop the bot.
python -m streamlit run ui\dashboard.py
endlocal
