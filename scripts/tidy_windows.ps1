# tidy_windows.ps1 - close the DEAD 'liquiditybot-runner' console shells left by
# repeated start.bat launches, and ONLY those. Never the live bot, never an
# unrelated window.
#
# Why this is safe: the runner is single-instance (SingleInstanceLock), so among
# the stacked 'liquiditybot-runner' windows AT MOST ONE has a live `python
# runner.py` child - that one IS the bot. Every other window is a dead cmd shell
# whose runner already exited on the lock (`cmd /k` just kept the empty console
# open). We identify each by its process tree and close only shells with NO
# python child; the single live runner (if any) is left running. No heartbeat
# guessing, no autostart side effects, no chance of dropping the bot.
#
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tidy_windows.ps1
#   (or double-click scripts\tidy_windows.bat)
$ErrorActionPreference = "Continue"
$self = $PID

# EXACT window title start.bat assigns (`start "liquiditybot-runner" ...`).
# Deliberately NOT '*liquiditybot*': the repo folder is 'liquiditybot_ab', so a
# broad match would force-kill VS Code ("<file> - liquiditybot_ab - Visual
# Studio Code"), an Explorer window on the folder, and this script's own
# console. The substring '-runner' appears in none of those.
$cands = Get-Process -Name cmd -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -ne $self -and
                   $_.MainWindowTitle -like '*liquiditybot-runner*' }

if (-not $cands) {
    Write-Host "No 'liquiditybot-runner' windows found - nothing to clean." -ForegroundColor Green
    exit 0
}

$closed = 0; $kept = 0
foreach ($p in $cands) {
    # Fail SAFE: a CIM error must NOT be read as 'no children' (which would
    # tree-kill the live runner). Only close when the query DEFINITIVELY
    # succeeded AND found zero python children; on any error, keep the window.
    $queryOk = $true
    try {
        $kids = @(Get-CimInstance Win32_Process `
            -Filter "ParentProcessId=$($p.Id)" -ErrorAction Stop)
    } catch {
        $queryOk = $false; $kids = @()
    }
    # ANY live child counts as alive — not just python: a runner-titled
    # window currently running git/pip/robocopy must never be tree-killed
    $live = @($kids)
    if (-not $queryOk) {
        $kept++
        Write-Host ("KEEP  pid {0}: could not enumerate children (CIM error) - NOT risking the bot." -f $p.Id) -ForegroundColor Yellow
        continue
    }
    if ($live.Count -gt 0) {
        $kept++
        Write-Host ("KEEP  pid {0}: {1} live child process(es) - leaving it alone." -f $p.Id, $live.Count) -ForegroundColor Yellow
        continue
    }
    Write-Host ("CLOSE pid {0}: dead shell (no runner child)" -f $p.Id) -ForegroundColor Cyan
    # tree-kill: Stop-Process on cmd would orphan any child; taskkill /T handles
    # the tree. Harmless here (a dead shell has none) and correct if one lingers.
    & taskkill /PID $p.Id /T /F 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $closed++ }
}

Write-Host ""
Write-Host ("Done. Closed {0} dead shell(s); kept {1} live runner window(s)." -f $closed, $kept) -ForegroundColor Green
if ($kept -eq 0) {
    Write-Host "No live runner window remains. If the bot should be running, start it:" -ForegroundColor Yellow
    Write-Host "  headless (recommended): scripts\install_autostart.bat   (then schtasks /Run /TN LiquidityBot)"
    Write-Host "  windowed:               start.bat"
} else {
    Write-Host "The bot is still running in its window. For a windowless always-on run, use scripts\install_autostart.bat." -ForegroundColor Gray
}
