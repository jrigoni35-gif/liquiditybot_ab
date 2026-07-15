# install_autostart.ps1 - register the always-on bot supervisor as a hidden
# Windows Task Scheduler task that starts at logon and self-restarts. Run once:
#     powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
# (or just double-run scripts\install_autostart.bat). Undo with
# scripts\uninstall_autostart.bat.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pyw  = Join-Path $root ".venv\Scripts\pythonw.exe"
$sup  = Join-Path $root "scripts\pc_supervisor.py"
$tmpl = Join-Path $root "scripts\liquiditybot_autostart.xml"

if (-not (Test-Path $pyw)) {
    Write-Host "pythonw not found at $pyw - run install.bat first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $sup))  { Write-Host "missing $sup"  -ForegroundColor Red; exit 1 }
if (-not (Test-Path $tmpl)) { Write-Host "missing $tmpl" -ForegroundColor Red; exit 1 }

$user = whoami                                   # DOMAIN\user or PC\user
$xml  = (Get-Content -Raw $tmpl).
            Replace("{{USER}}", $user).
            Replace("{{PYTHONW}}", $pyw).
            Replace("{{SUPERVISOR}}", $sup).
            Replace("{{WORKDIR}}", $root)

$out = Join-Path $env:TEMP "liquiditybot_autostart.filled.xml"
# Task Scheduler requires UTF-16 (the XML header declares it)
[IO.File]::WriteAllText($out, $xml, [Text.Encoding]::Unicode)

schtasks /Create /TN "LiquidityBot" /XML $out /F
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Installed 'LiquidityBot' autostart (hidden, at logon, self-restart)." -ForegroundColor Green
    Write-Host "Start it now without waiting for a re-logon:"
    Write-Host "    schtasks /Run /TN LiquidityBot"
    Write-Host "Watch it:  type outputs\pc_supervisor.log"
    Write-Host "Remove it: scripts\uninstall_autostart.bat"
} else {
    Write-Host "schtasks import failed (exit $LASTEXITCODE)." -ForegroundColor Red
}
Remove-Item $out -ErrorAction SilentlyContinue
