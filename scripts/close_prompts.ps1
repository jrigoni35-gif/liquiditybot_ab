# close_prompts.ps1 - ONE-SHOT: close every DEAD Command Prompt window.
# Deployed at the operator's request (2026-07-20) after the console-popup fix:
# popups are stopped at the source; this sweeps away the dead shells the old
# code left open. pc_supervisor runs it ONCE (stamp outputs/.prompt_sweep_done,
# windowless); delete the stamp to run it again.
#
# DEAD = a classic cmd.exe window hosting NO child process — nothing is
# running inside it (the `cmd /k` leftovers whose bot/git child exited long
# ago). Scope guarantees:
#   * a prompt with ANY live child (something actually running) is NEVER
#     touched — enumeration failure counts as "has children" (fail-safe);
#   * polite WM_CLOSE first; force only a dead shell that refuses (it hosts
#     nothing, so nothing can be lost);
#   * classic cmd.exe only — Windows Terminal / PowerShell are never touched.
$self = $PID
$cands = @(Get-Process -Name cmd -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -and $_.Id -ne $self })
if (-not $cands) { exit 0 }

$dead = @()
foreach ($p in $cands) {
    try {
        $kids = @(Get-CimInstance Win32_Process `
            -Filter "ParentProcessId=$($p.Id)" -ErrorAction Stop)
    } catch {
        continue                       # can't verify -> treat as ALIVE, skip
    }
    if ($kids.Count -eq 0) { $dead += $p }
}
if (-not $dead) { exit 0 }

foreach ($p in $dead) {
    try { $null = $p.CloseMainWindow() } catch { }
}
Start-Sleep -Seconds 2
foreach ($p in $dead) {
    try {
        if (-not $p.HasExited) {
            # still no children (re-check: a child could have started in the
            # grace window) -> empty shell refusing WM_CLOSE; safe to end
            $kids = @(Get-CimInstance Win32_Process `
                -Filter "ParentProcessId=$($p.Id)" -ErrorAction Stop)
            if ($kids.Count -eq 0) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            }
        }
    } catch { }
}
