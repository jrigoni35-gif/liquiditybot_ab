# close_prompts.ps1 - ONE-SHOT: close every DEAD Command Prompt window.
# pc_supervisor runs it once (stamp outputs/.prompt_sweep_done2, windowless).
# Every action is logged to outputs/prompt_sweep.log so the one shot is
# verifiable (found / closed / forced / kept), never silent.
#
# DEAD = a classic cmd.exe hosting NO child process (nothing running inside).
# Ladder:
#   1. polite WM_CLOSE (CloseMainWindow) for every dead cmd WITH a window —
#      load-bearing: on classic conhost the console window is attributed to
#      the attached cmd.exe (win32k ownership shim), so MainWindowHandle
#      resolves and WM_CLOSE reaches conhost -> CTRL_CLOSE_EVENT -> cmd exits;
#   2. force ONLY dead shells carrying the liquiditybot runner signature in
#      their CommandLine (start.bat's `cmd /k ... python runner.py`) — never
#      an arbitrary refusing prompt;
#   3. Windows-Terminal fallback: on WT-default machines a dead cmd has NO
#      attributable window (ConPTY; MainWindowTitle empty) — those are closed
#      by runner-signature match + childless check via Stop-Process (safe:
#      the shell hosts nothing; WT reaps the pane).
# A prompt with ANY live child is NEVER touched; CIM enumeration failure
# counts as alive (fail-safe). Windows Terminal / PowerShell processes are
# never targeted.
$self = $PID
$logDir = Join-Path (Split-Path -Parent $PSScriptRoot) "outputs"
$log = Join-Path $logDir "prompt_sweep.log"
function Note($m) {
    try {
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $log -Value "$ts prompt_sweep: $m" -ErrorAction SilentlyContinue
    } catch { }
}

$RUNNER_SIG = 'liquiditybot|runner\.py'
$cands = @(Get-Process -Name cmd -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -ne $self })
Note ("scan: {0} cmd process(es)" -f $cands.Count)
if (-not $cands) { Note "nothing to do"; exit 0 }

$closed = 0; $forced = 0; $kept = 0
$deadWindowed = @(); $deadRunnerNoWin = @()
foreach ($p in $cands) {
    try {
        $row = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction Stop
        $kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" -ErrorAction Stop)
    } catch {
        $kept++; Note ("keep pid {0}: CIM enumeration failed (treated alive)" -f $p.Id)
        continue                       # can't verify -> ALIVE, never touch
    }
    if ($kids.Count -gt 0) {
        $kept++; Note ("keep pid {0}: {1} live child(ren)" -f $p.Id, $kids.Count)
        continue
    }
    if ($p.MainWindowTitle) {
        $deadWindowed += $p
    } elseif ("$($row.CommandLine)" -match $RUNNER_SIG) {
        $deadRunnerNoWin += $p         # WT-hosted dead runner shell
    } else {
        $kept++; Note ("keep pid {0}: dead but windowless + no runner signature" -f $p.Id)
    }
}

foreach ($p in $deadWindowed) {
    try { $null = $p.CloseMainWindow(); $closed++
          Note ("close pid {0}: WM_CLOSE ({1})" -f $p.Id, $p.MainWindowTitle) } catch { }
}
if ($deadWindowed) { Start-Sleep -Seconds 2 }
foreach ($p in $deadWindowed) {
    try {
        if (-not $p.HasExited) {
            $row = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)" -ErrorAction Stop
            $kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" -ErrorAction Stop)
            if ($kids.Count -eq 0 -and ("$($row.CommandLine)" -match $RUNNER_SIG)) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                $forced++; Note ("force pid {0}: dead runner shell refused WM_CLOSE" -f $p.Id)
            } else {
                $kept++; Note ("keep pid {0}: refused WM_CLOSE, not a runner shell" -f $p.Id)
            }
        }
    } catch { }
}
foreach ($p in $deadRunnerNoWin) {
    try {
        $kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" -ErrorAction Stop)
        if ($kids.Count -eq 0) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $forced++; Note ("force pid {0}: WT-hosted dead runner shell (no window)" -f $p.Id)
        }
    } catch { }
}
Note ("done: {0} closed, {1} forced, {2} kept" -f $closed, $forced, $kept)
