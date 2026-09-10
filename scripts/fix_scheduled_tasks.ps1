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
# CORRECTED 2026-09-10 - THIS SCRIPT DID NOT FIX THE TASKS THAT MATTER.
# The paragraph above names KeepAlive-10m as a "control" and then the loop below
# converted only Checkin-4h and LearningPanel-Daily. Re-measured 2026-09-10, all
# FOUR LiquidityBot* tasks are LogonType=Interactive - including `LiquidityBot`
# itself, which starts pc_supervisor (the process that keeps the runner and both
# Grafana pushers alive), and KeepAlive-10m, which is not a control at all but the
# INDEPENDENT WATCHDOG: scripts/keepalive.py relaunches runner.py whenever
# status.json is >900s or the lock heartbeat >60s stale. Converting two of four
# left the bot and its watchdog dying together on logoff - which is the 21-hour
# outage, not a cosmetic miss. NumberOfMissedRuns now reads 0 on all four, so the
# counter that motivated the original script has reset and is no longer evidence;
# LogonType is.
#
# AND S4U ALONE IS NOT ENOUGH FOR `LiquidityBot`. Its only trigger is
# MSFT_TaskLogonTrigger, so after a reboot with nobody logging on it never fires
# regardless of principal: S4U governs whether a task MAY run without an
# interactive session, the TRIGGER governs whether anything starts it. An
# AtStartup trigger is added alongside the logon one below. A double start is
# harmless - pc_supervisor and the runner both hold single-instance locks and the
# task's MultipleInstances=IgnoreNew drops the duplicate.
#
# Two further silent-failure settings, measured the same day and fixed below:
# KeepAlive-10m had DisallowStartIfOnBatteries=True (a watchdog that declines to
# run on battery) and StartWhenAvailable=False (a missed run skipped rather than
# caught up).
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
# To remove the boot trigger:  Set-ScheduledTask -TaskName LiquidityBot -Trigger
#   @((Get-ScheduledTask LiquidityBot).Triggers | Where-Object {
#       $_.CimClass.CimClassName -ne 'MSFT_TaskBootTrigger' })
# The loop is IDEMPOTENT: an already-S4U task keeps its principal and a task that
# already has a boot trigger does not get a second one, so re-running is safe.
# Running tasks are NOT stopped - Set-ScheduledTask rewrites the stored definition
# only; a live pc_supervisor keeps running and picks the change up at next start.
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

# --- 1. ALL FOUR tasks: InteractiveToken -> S4U ----------------------------
# Was two. Measured 2026-09-10: all four LiquidityBot* tasks are
# LogonType=Interactive, and the two the original loop OMITTED are the two that
# matter - `LiquidityBot` (starts pc_supervisor, which keeps the runner and both
# Grafana pushers alive) and `LiquidityBot-KeepAlive-10m` (the independent
# watchdog that relaunches runner.py when status.json is >900s or the lock
# heartbeat >60s stale). Converting only Checkin and LearningPanel left the bot
# AND its watchdog dying together on logoff - exactly the 21-hour outage.
#
# S4U IS NOT SUFFICIENT ON ITS OWN FOR `LiquidityBot`, and this is the part the
# original premise missed: that task's only trigger is MSFT_TaskLogonTrigger, so
# after a reboot with nobody logging on it never fires no matter what its
# principal says. S4U governs "may it run without an interactive session"; the
# TRIGGER governs "does anything start it". A boot trigger is added below so the
# supervisor comes up with the machine. The logon trigger is KEPT - a second
# start is harmless: pc_supervisor and the runner both hold single-instance
# locks, and the task's own MultipleInstances=IgnoreNew drops the duplicate.
#
# Per-task settings fixes, also measured rather than assumed:
#   KeepAlive-10m  DisallowStartIfOnBatteries=True  -> False
#       A laptop on battery silently does not run the watchdog. A watchdog that
#       declines to run in the conditions where it is most needed is not one.
#   KeepAlive-10m  StartWhenAvailable=False -> True
#       Same "late beats silently skipped" argument the original applied to the
#       other two, never applied here.
#
# Identity: the tasks currently run as bare `johnmason`; $user resolves to
# DESKTOP-OS02KQS\johnmason, which is the SAME principal (verified with whoami),
# so rewriting the principal does not reassign the account.
#
# IDEMPOTENT: a task already on S4U has its principal left alone, so re-running
# this is safe. Running tasks are NOT stopped - Set-ScheduledTask updates the
# stored definition; the live pc_supervisor keeps running and the change takes
# effect at its next start.

$targets = @(
    @{ Name = 'LiquidityBot';                     AddBootTrigger = $true  },
    @{ Name = 'LiquidityBot-KeepAlive-10m';       OnBattery      = $true  },
    @{ Name = 'LiquidityBot-Checkin-4h';                                  },
    @{ Name = 'LiquidityBot-LearningPanel-Daily';                         }
)

foreach ($spec in $targets) {
    $name = $spec.Name
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) { Write-Warning "$name not found - skipping"; continue }

    $before = ($task | Get-ScheduledTaskInfo).NumberOfMissedRuns
    Write-Host "$name : LogonType=$($task.Principal.LogonType) State=$($task.State) missedRuns=$before"

    if ($task.Principal.LogonType -eq 'S4U') {
        Write-Host "  already S4U - principal untouched" -ForegroundColor DarkGray
    } else {
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel $task.Principal.RunLevel
        Set-ScheduledTask -TaskName $name -Principal $principal | Out-Null
    }

    # StartWhenAvailable lets a missed run catch up instead of waiting for the
    # next scheduled slot - the difference between "late" and "silently skipped".
    $settings = (Get-ScheduledTask -TaskName $name).Settings
    $settings.StartWhenAvailable = $true
    if ($spec.OnBattery) {
        $settings.DisallowStartIfOnBatteries = $false
        $settings.StopIfGoingOnBatteries    = $false
    }
    Set-ScheduledTask -TaskName $name -Settings $settings | Out-Null

    # A logon-only trigger cannot survive a reboot with no logon, whatever the
    # principal says. Add AtStartup alongside it, never replacing it.
    if ($spec.AddBootTrigger) {
        $cur = (Get-ScheduledTask -TaskName $name).Triggers
        $hasBoot = @($cur | Where-Object { $_.CimClass.CimClassName -eq 'MSFT_TaskBootTrigger' }).Count -gt 0
        if ($hasBoot) {
            Write-Host "  boot trigger already present" -ForegroundColor DarkGray
        } else {
            $boot = New-ScheduledTaskTrigger -AtStartup
            Set-ScheduledTask -TaskName $name -Trigger @($cur + $boot) | Out-Null
            Write-Host "  + AtStartup trigger added (logon trigger kept)" -ForegroundColor Green
        }
    }

    $after = Get-ScheduledTask -TaskName $name
    $trig  = ($after.Triggers | ForEach-Object { $_.CimClass.CimClassName -replace 'MSFT_Task','' }) -join ','
    Write-Host ("  -> LogonType={0} StartWhenAvailable={1} OnBattery={2} triggers={3}" -f `
        $after.Principal.LogonType, $after.Settings.StartWhenAvailable, `
        (-not $after.Settings.DisallowStartIfOnBatteries), $trig) -ForegroundColor Green
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
