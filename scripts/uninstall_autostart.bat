@echo off
REM uninstall_autostart.bat - remove the always-on task and stop the supervisor.
setlocal
echo Stopping and removing the LiquidityBot autostart task...
schtasks /End    /TN "LiquidityBot" >nul 2>nul
schtasks /Delete /TN "LiquidityBot" /F
echo.
echo Task removed. The bot may still be running from this session - use stop.bat
echo to stop the runner, or reboot. (Grafana pushers stop on their own next tick.)
echo.
pause
