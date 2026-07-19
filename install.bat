@echo off
REM install.bat - ONE command to set everything up (Windows).
REM Creates .venv, installs all dependencies, verifies.
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo Python launcher 'py' not found. Install Python 3.10+ from python.org
    echo and check "Add python.exe to PATH" during install, then re-run this.
    exit /b 1
)

if not exist .venv (
    echo [1/3] Creating virtual environment...
    py -3 -m venv .venv || exit /b 1
) else (
    echo [1/3] Virtual environment already exists - reusing.
)

call .venv\Scripts\activate.bat
echo [2/3] Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q || exit /b 1

echo [3/3] Verifying installation...
python -m compileall -q . >nul || exit /b 1
python -c "import main, runner" >nul 2>nul || (
    echo Import check FAILED - see errors above. & exit /b 1
)

echo.
echo ============================================
echo  Install complete. Everything you need:
echo    start.bat  - run the bot
echo    stop.bat   - stop the bot cleanly
echo    test_windows.bat - run the full test matrix
echo  The bot starts in DRY RUN (paper trading).
echo  Going live requires editing config.json AND
echo  typing the ARM phrase (ARM LIVE) at the PC console.
echo ============================================
endlocal
