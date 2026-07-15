@echo off
REM install_autostart.bat - one-click: register the hidden always-on task.
REM Runs the PowerShell installer with an execution-policy bypass (no global
REM policy change). Undo with uninstall_autostart.bat.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_autostart.ps1"
echo.
pause
