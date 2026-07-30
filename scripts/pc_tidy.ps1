# pc_tidy.ps1 - one canonical bot home, everything else found and removed.
#
# TANK program checkpoint C1 (docs/superpowers/specs/
# 2026-07-30-tank-program-design.md). Report-first: run with no arguments
# to SEE what would happen; nothing is touched until -Apply. Removals go
# to the Recycle Bin, never hard-delete. Any candidate that contains
# learning data (signal history, audit/event chains, snapshots) is NEVER
# removed - it is flagged loudly for a human decision instead.
#
# Usage (from the canonical checkout):
#   powershell -ExecutionPolicy Bypass -File scripts\pc_tidy.ps1          # report
#   powershell -ExecutionPolicy Bypass -File scripts\pc_tidy.ps1 -Apply  # recycle
param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName Microsoft.VisualBasic | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null

# Canonical home = parent of the scripts/ dir this file lives in.
$Canonical = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path.TrimEnd("\")
# Token store lives outside the repo on purpose (survives re-clones).
$TokenDir = Join-Path $env:USERPROFILE ".liquiditybot"

$DataMarkers = @(
    "outputs\signal_history.csv", "outputs\audit.jsonl",
    "outputs\events.jsonl", "outputs\status.json"
)

function Test-DirHasData([string]$dir) {
    # Recursive: a stale checkout may nest its outputs/ one level down
    # (e.g. Backup\liquiditybot_ab\outputs\...) - a shallow check misses it.
    $names = @("signal_history.csv", "audit.jsonl", "events.jsonl",
               "status.json")
    $found = Get-ChildItem $dir -Recurse -Depth 4 -File -Force `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Length -gt 0 -and
            $_.Directory.FullName -imatch "\\outputs(\\|$)" -and
            ($names -contains $_.Name -or
             $_.Directory.FullName -imatch "\\outputs\\snapshots(\\|$)")
        } | Select-Object -First 1
    if ($found) { return $found.FullName.Substring($dir.Length).TrimStart("\") }
    return $null
}

function Test-ZipHasData([string]$zipPath) {
    try { $z = [System.IO.Compression.ZipFile]::OpenRead($zipPath) }
    catch { return "unreadable-zip" }  # can't prove it's data-free -> keep
    try {
        $names = @("signal_history.csv", "audit.jsonl", "events.jsonl",
                   "status.json")
        foreach ($e in $z.Entries) {
            $leaf = Split-Path $e.FullName -Leaf
            if ($e.FullName -match "(^|/)outputs/" -and $e.Length -gt 0 -and
                ($names -contains $leaf -or
                 $e.FullName -match "(^|/)outputs/snapshots/")) {
                return $e.FullName
            }
        }
        return $null
    } finally { $z.Dispose() }
}

function Send-ToRecycleBin($item) {
    if ($item.PSIsContainer) {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
            $item.FullName, "OnlyErrorDialogs", "SendToRecycleBin")
    } else {
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $item.FullName, "OnlyErrorDialogs", "SendToRecycleBin")
    }
}

# ---- scan -----------------------------------------------------------------
$roots = @(
    (Join-Path $env:USERPROFILE "Desktop"),
    (Join-Path $env:USERPROFILE "Downloads"),
    (Join-Path $env:USERPROFILE "Documents"),
    $env:USERPROFILE
)
if ($env:OneDrive) { $roots += (Join-Path $env:OneDrive "Desktop") }
$roots = $roots | Where-Object { Test-Path $_ } | Select-Object -Unique

$hits = @()
foreach ($root in $roots) {
    $depth = if ($root -eq $env:USERPROFILE) { 0 } else { 2 }
    $items = Get-ChildItem $root -Depth $depth -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -imatch "liquidit" }
    $hits += $items
}
# Also catch shortcuts pointing at bot paths.
$shell = New-Object -ComObject WScript.Shell
$links = foreach ($root in $roots) {
    Get-ChildItem $root -Depth 1 -Filter *.lnk -Force -ErrorAction SilentlyContinue |
        Where-Object {
            try { $shell.CreateShortcut($_.FullName).TargetPath -imatch "liquidit" }
            catch { $false }
        }
}
$hits += $links

# Keep top-most matches only; exclude the canonical tree, the token dir,
# and recycle-bin leftovers.
$keepRx = [regex]::Escape($Canonical)
$tokRx = [regex]::Escape($TokenDir)
$hits = $hits | Sort-Object FullName -Unique | Where-Object {
    $_.FullName -notmatch "^$keepRx(\\|$)" -and
    $_.FullName -notmatch "^$tokRx(\\|$)" -and
    $_.FullName -notmatch '\$Recycle\.Bin'
}
$tops = @()
foreach ($h in $hits) {
    $covered = $tops | Where-Object {
        $h.FullName -like ($_.FullName + "\*") }
    if (-not $covered) { $tops += $h }
}

# An ANCESTOR of the canonical home (e.g. Documents\liquiditybot, the
# parent of the checkout) must never be recycled - recycling it takes the
# live bot with it. Descend into ancestors and keep only their stray
# children as candidates.
$ancestorNotes = @()
$queue = New-Object System.Collections.Queue
foreach ($t in $tops) { $queue.Enqueue($t) }
$tops = @()
while ($queue.Count -gt 0) {
    $t = $queue.Dequeue()
    if ($t.FullName -ieq $Canonical) { continue }
    if ($t.PSIsContainer -and ($Canonical -like ($t.FullName + "\*"))) {
        $ancestorNotes += "kept (parent of the live bot): $($t.FullName) - only strays inside it are candidates"
        Get-ChildItem $t.FullName -Force -ErrorAction SilentlyContinue |
            ForEach-Object { $queue.Enqueue($_) }
        continue
    }
    $tops += $t
}

# ---- report / apply -------------------------------------------------------
Write-Host "canonical home : $Canonical"
Write-Host "token store    : $TokenDir  (kept - bot credentials)"
Write-Host ("mode           : " + $(if ($Apply) { "APPLY (recycle)" }
                                    else { "REPORT ONLY" }))
foreach ($n in $ancestorNotes) { Write-Host $n }
Write-Host ""

if (-not $tops) { Write-Host "nothing found outside the canonical home - already clean." }

$blocked = 0
foreach ($t in $tops) {
    $data = $null
    if ($t.PSIsContainer) { $data = Test-DirHasData $t.FullName }
    elseif ($t.Extension -ieq ".zip") { $data = Test-ZipHasData $t.FullName }
    elseif ($t.Name -imatch "signal_history|\.jsonl$|^status\.json$|snapshot") {
        $data = "data-like filename"
    }
    if ($data) {
        $blocked++
        Write-Host "KEEP (HAS DATA!) $($t.FullName)"
        Write-Host "                 -> contains: $data  - decide by hand, never auto-removed"
        continue
    }
    if ($Apply) {
        Send-ToRecycleBin $t
        Write-Host "RECYCLED         $($t.FullName)"
    } else {
        Write-Host "would recycle    $($t.FullName)"
    }
}

# ---- post-checks ----------------------------------------------------------
Write-Host ""
Write-Host "-- scheduled tasks referencing the bot --"
Get-ScheduledTask -ErrorAction SilentlyContinue | ForEach-Object {
    $acts = ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " "
    $wd = ($_.Actions | ForEach-Object { $_.WorkingDirectory }) -join " "
    if ("$acts $wd" -imatch "liquidit") {
        $ok = ("$acts $wd" -imatch $keepRx)
        Write-Host ("  [{0}] {1}" -f $(if ($ok) { "OK" } else { "WRONG PATH" }), $_.TaskName)
    }
}
Write-Host "-- live bot processes --"
Write-Host "   (each logical process shows TWICE: venv shim + base interpreter pair - normal)"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -imatch "liquidit" } |
    ForEach-Object { Write-Host ("  pid {0}: {1}" -f $_.ProcessId,
        ($_.CommandLine -replace '^.*\\', '')) }

if ($blocked -gt 0) {
    Write-Host ""
    Write-Host "$blocked item(s) held back because they contain learning data."
    exit 2
}
