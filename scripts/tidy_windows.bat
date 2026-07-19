@echo off
REM tidy_windows.bat - one-click: clear stacked bot console windows safely.
REM Ensures the hidden always-on supervisor is running, then closes the stray
REM `cmd /k` windows left behind by repeated start.bat launches. The bot never
REM goes down (the headless supervisor keeps the windowless runner alive).
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tidy_windows.ps1"
echo.
pause
