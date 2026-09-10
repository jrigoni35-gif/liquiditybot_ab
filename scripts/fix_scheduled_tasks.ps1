# scripts/fix_scheduled_tasks.ps1 - operator maintenance, RUN ELEVATED.
#
# WHY THIS EXISTS (measured 2026-09-09 on DESKTOP-OS02KQS):
#   LiquidityBot-Checkin-4h          NumberOfMissedRuns=6, last run 2026-09-08 15:31
#   LiquidityBot-LearningPanel-Daily NumberOfMissedRuns=1, skipped 2026-09-09
# Both report LastTaskResult=0 when they DO run, so nothing fails loudly - the runs
# are SKIPPED, not failed. Root cause, from Task Scheduler operational log Event ID
# 332 counted two independent ways: both tasks run as Principal LogonType
# =InteractiveToken, which requires a live interactive session to be present. With
# no one logged in, the run is skipped. The KeepAlive-10m control has the identical
# settings and also gets skipped (126 times) - it just fires again in ten minutes,
# so it never looks broken. S4U ("run whether user is logged on or not", without
# storing a password) removes the dependency.
#
# It ALSO registers the missing daily candle backfill. Measured the same day: the
# 86400s Kraken lane's last bar was 2026-08-28 (13 days stale) and held exactly 720
# bars - Kraken's OHLC page limit - i.e. a one-shot backfill nothing appends to.
# scripts/candle_collect.py is hardcoded to BAR_INTERVAL_S = 300 and collects only
# 5-minute bars, so no daily bars were ever being appended. Without this task,
# scripts/regime_chain_report.py correctly refuses to name a current regime and the
# daily learning panel reports on a frozen corpus.
#
# Registration is at 05:00, twenty-five minutes ahead of LiquidityBot-LearningPanel
# -Daily (05:30), so the panel reports on data refreshed the same morning.
#
# EVERYTHING HERE IS REVERSIBLE. To undo the new task:
#   Unregister-ScheduledTask -TaskName LiquidityBot-CandleBackfill-Daily -Confirm:$false
# To revert a principal, re-run Set-ScheduledTask with -LogonType InteractiveToken.
#
# This script changes NOTHING inside the bot: no order, no size, no stop, no fee, no
# fill, no dry_run. scripts/candle_backfill.py is SAFE class by its own header -
# read-only public GETs, appends only into outputs/candles/, imported by nothing in
# the decision path, and it builds its own feed clients rather than borrowing the
# engine's (a backfill on the engine's client would serialize against live order
# placement through ThrottledRestClient's lock).

#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\haird\Documents\liquiditybot\liquiditybot_ab'
$user = "$env:COMPUTERNAME\$env:USERNAME"

Write-Host "Principal will be: $user" -ForegroundColor Cyan
Write-Host ""

# --- 1. the two degraded tasks: InteractiveToken -> S4U --------------------
foreach ($name in @('LiquidityBot-Checkin-4h', 'LiquidityBot-LearningPanel-Daily')) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) { Write-Warning "$name not found - skipping"; continue }

    $before = ($task | Get-ScheduledTaskInfo).NumberOfMissedRuns
    Write-Host "$name : LogonType=$($task.Principal.LogonType) missedRuns=$before"

    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
    Set-ScheduledTask -TaskName $name -Principal $principal | Out-Null

    # StartWhenAvailable lets a missed run catch up instead of waiting for the
    # next scheduled slot - the difference between "late" and "silently skipped".
    $settings = $task.Settings
    $settings.StartWhenAvailable = $true
    Set-ScheduledTask -TaskName $name -Settings $settings | Out-Null

    $after = Get-ScheduledTask -TaskName $name
    Write-Host "  -> LogonType=$($after.Principal.LogonType) StartWhenAvailable=$($after.Settings.StartWhenAvailable)" -ForegroundColor Green
}

Write-Host ""

# --- 2. register the daily candle backfill ---------------------------------
$backfill = 'LiquidityBot-CandleBackfill-Daily'
if (Get-ScheduledTask -TaskName $backfill -ErrorAction SilentlyContinue) {
    Write-Host "$backfill already exists - leaving it alone" -ForegroundColor Yellow
}
else {
    $action = New-ScheduledTaskAction `
        -Execute "$repo\.venv\Scripts\python.exe" `
        -Argument 'scripts\candle_backfill.py --venue kraken --quote USD --symbols PAXG,ETH,BTC,LINK --interval 86400' `
        -WorkingDirectory $repo

    $trigger = New-ScheduledTaskTrigger -Daily -At 5:00am

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
        -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries

    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited

    Register-ScheduledTask -TaskName $backfill -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal `
        -Description 'Daily Kraken daily-bar backfill into the SAFE-class candle store; feeds regime_chain_report and the 05:30 learning panel. Remove with: Unregister-ScheduledTask -TaskName LiquidityBot-CandleBackfill-Daily -Confirm:$false' | Out-Null

    Write-Host "$backfill registered (daily 05:00, S4U)" -ForegroundColor Green
}

# --- 3. read back; NEXT RUN is the field that matters, not State -----------
Write-Host ""
Write-Host "State is not the field to read - a task can sit 'Ready' for weeks. Read Next Run:" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -match 'LiquidityBot' } | ForEach-Object {
    $i = $_ | Get-ScheduledTaskInfo
    '{0,-34} logon={1,-16} missed={2,-3} next={3}' -f `
        $_.TaskName, $_.Principal.LogonType, $i.NumberOfMissedRuns, $i.NextRunTime
}

Write-Host ""
Write-Host "Verify tomorrow: NumberOfMissedRuns should stop climbing, and" -ForegroundColor Cyan
Write-Host "  python scripts/regime_chain_report.py" -ForegroundColor Cyan
Write-Host "should print an HMM vote rather than 'NO CURRENT-STATE CLAIM'." -ForegroundColor Cyan
