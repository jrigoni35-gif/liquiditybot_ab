@echo off
REM stop.bat - stop the bot cleanly (snapshots state, cancels resting orders
REM via the venue dead-man switch, exits the loop between cycles).
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python -c "import sys; sys.path.insert(0, '.'); from core.runtime import ControlChannel; ControlChannel('outputs/control').send('stop'); print('stop sent - the runner exits after its current cycle.')"
endlocal
