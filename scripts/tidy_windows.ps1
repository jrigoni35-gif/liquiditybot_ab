# tidy_windows.ps1 - clear stacked bot console windows WITHOUT dropping the bot.
#
# The stacked cascade is redundant `start.bat` windows: each ran `cmd /k python
# runner.py`, the SingleInstanceLock refused the duplicate engine, but `cmd /k`
# left the empty shell open. This script closes them safely by first making sure
# the bot is running HEADLESS under the LiquidityBot scheduled task (pythonw ->
# pc_supervisor -> windowless runner), so closing the visible windows can never
# take the bot down - the hidden supervisor re-spawns the runner windowless
# within ~30s if a closed window happened to hold the lock.
#
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tidy_windows.ps1
#   (or just double-click scripts\tidy_windows.bat)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$py   = Join-Path $root ".venv\Scripts\python.exe"
$alive = Join-Path $root "scripts\bot_alive.py"

function Bot-Alive {
    if (-not (Test-Path $py)) { return $false }
    & $py $alive | Out-Null
    return ($LASTEXITCODE -eq 0)
}

# 1) Ensure the headless supervisor exists and is running, so the bot is safe
#    once the visible windows go away.
$haveTask = $false
schtasks /Query /TN "LiquidityBot" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $haveTask = $true }

if (-not $haveTask) {
    Write-Host "LiquidityBot autostart task not found - installing it (hidden, at logon)..." -ForegroundColor Yellow
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "install_autostart.ps1")
}
Write-Host "Starting the hidden supervisor (idempotent - MultipleInstancesPolicy=IgnoreNew)..."
schtasks /Run /TN "LiquidityBot" 2>$null | Out-Null

# 2) Wait for a fresh heartbeat so we KNOW the headless bot is holding the fort
#    before we close anything.
$ok = $false
foreach ($i in 1..30) {
    if (Bot-Alive) { $ok = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $ok) {
    Write-Host "No fresh heartbeat yet - NOT closing any windows (won't risk the bot)." -ForegroundColor Red
    Write-Host "Check outputs\pc_supervisor.log and outputs\status.json, then re-run." -ForegroundColor Red
    exit 1
}

# 3) Close every visible liquiditybot console. The `start "liquiditybot-runner"`
#    title makes them findable; also match any cmd/python window whose title
#    mentions liquiditybot. The hidden supervisor (pythonw, no MainWindowTitle)
#    and its windowless runner are never matched.
$mine = @($PID)
$targets = Get-Process |
    Where-Object {
        $_.Id -notin $mine -and
        $_.MainWindowTitle -and
        ($_.MainWindowTitle -like "*liquiditybot*")
    }

if (-not $targets) {
    Write-Host "No stray liquiditybot windows found - nothing to close. Bot is up." -ForegroundColor Green
    exit 0
}

Write-Host ("Closing {0} stray window(s):" -f $targets.Count) -ForegroundColor Cyan
foreach ($p in $targets) {
    Write-Host ("  pid {0}  [{1}]  {2}" -f $p.Id, $p.ProcessName, $p.MainWindowTitle)
    try { $null = $p.CloseMainWindow() } catch { }
}
Start-Sleep -Seconds 2
# Force any that ignored the polite close (cmd /k won't honor CloseMainWindow
# while a child is attached).
foreach ($p in $targets) {
    if (-not $p.HasExited) { try { Stop-Process -Id $p.Id -Force } catch { } }
}

# 4) Confirm the bot is still alive after the sweep (supervisor re-spawns the
#    windowless runner if one of the closed windows held the lock).
Start-Sleep -Seconds 3
$ok = $false
foreach ($i in 1..30) {
    if (Bot-Alive) { $ok = $true; break }
    Start-Sleep -Seconds 3
}
if ($ok) {
    Write-Host "Done. Stray windows closed; bot heartbeat is fresh (running headless)." -ForegroundColor Green
} else {
    Write-Host "Windows closed, but heartbeat went stale. The supervisor should" -ForegroundColor Yellow
    Write-Host "relaunch within ~30s; watch outputs\pc_supervisor.log." -ForegroundColor Yellow
}
