@echo off
REM restart.bat - pull the latest code and bounce ONLY the runner, so the hidden
REM always-on supervisor relaunches it on the new commit. Use this when a deploy
REM needs to reach the running bot and the soft-stop path is wedged (e.g. a
REM long-lived runner whose command consumption stopped honoring 'stop').
REM
REM It force-kills ONLY the python process running runner.py. The supervisor and
REM the Grafana pushers are left running, and the supervisor relaunches the
REM runner on the new code within a minute or two (heartbeat-gated). stop.bat is
REM NOT enough here - it sends the same soft 'stop' the wedged runner ignores.
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"

echo [restart] pulling latest code (fast-forward only)...
git pull --ff-only

echo [restart] force-killing the runner (supervisor relaunches it on the new code)...
REM match python.exe AND pythonw.exe: the hidden supervisor launches the runner
REM under pythonw, so the old python.exe-only filter silently killed NOTHING on
REM an autostart install (the deploy never actually bounced the runner).
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*runner.py*' };" ^
  "if ($p) { $p | ForEach-Object { Write-Host ('  killing runner pid ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force } }" ^
  "else { Write-Host '  no runner.py process found (supervisor will start one)' }"

echo.
echo [restart] done. The supervisor relaunches the runner within ~1-2 min.
echo           If it does not come back, run start.bat.
endlocal
