# Machine Optimization Plan — 2026-08-28

Synthesis of census + four lenses (services/startup, disk, PATH/env/config, tooling-gap).
All sizes/counts verbatim from lens snapshots (2026-08-27 ~16:30–20:2x local; tooling
~00:5xZ 08-28). ZERO new measurements. A separate fixer applies approved actions later;
this document is read-only evidence + plan.

## NEVER-TOUCH LIST (binding — flag, never act)

- Live liquiditybot runner process + its `outputs/`
- ALL Windows scheduled tasks containing `liquiditybot`, `checkin`, `deploy`
  (silently-expired-task incident 2026-08-16 — load-bearing)
- Both Obsidian vaults: `Documents\liquiditybot\vault` (canonical) AND
  `C:\Users\haird\vaults\liquiditybot` (retired, preservation-protected, operator
  decision open)
- `Documents\liquiditybot_isolated_2026-08-11` (preservation copy)
- `D:\Archive` (Hummingbot vhdx, preserved by operator order)
- `E:` drive entirely
- The repo `.venv`
- VS BuildTools install currently in progress (incl. HKLM RunOnce
  `setup.exe resume ...BuildTools` key and `%TEMP%\WinGet\vs_BuildTools.exe`)
- Parked LLVM at `C:\Program Files\LLVM` (deliberately off PATH, pending STL)
- `~\.claude` session/memory/transcript data
- Resume project at `Documents\resume`

Flagged-only notes inside never-touch scope (verify, do not act):
- Checkin-4h + KeepAlive-10m tasks are again "One Time Only, Hourly/Minute" trigger
  shape (the 2026-08-16 incident shape). Next Run times valid (11:31 PM / 8:31 PM) but
  /v did not show repetition duration bound — operator/fixer should verify
  `Repeat: Until: Duration = Indefinite` via `Export-ScheduledTask`. NEVER-TOUCH.
- Tasks run as user `johnmason` while profile is `haird` (account rename, cosmetic);
  anyone re-registering must use the current account/SID, not the display name.

---

## 1. AUTO-APPLY (reversible, zero-risk)

| # | Action | Size | Command | Undo story |
|---|---|---|---|---|
| A1 | Purge pip cache | 215.3 MB | `pip cache purge` (any interpreter; cache at `%LOCALAPPDATA%\pip\cache`) | Regenerable — pip re-downloads on demand |
| A2 | Purge npm cache | 77.7 MB | `npm cache clean --force` (`%LOCALAPPDATA%\npm-cache`) | Regenerable — npm re-fetches |
| A3 | Delete OLD claude session scratchpad `011c090c-f289-...` (lastwrite 2026-08-21, not current) | 119.4 MB | `Remove-Item -Recurse -Force "$env:TEMP\claude\c--Users-haird-Documents-liquiditybot-liquiditybot-ab\011c090c-f289-*"` | Regenerable-class (dead session scratch). CONSTRAINT: current session dir `cdb03d59` (6.5 MB, live) must NOT match the glob — delete by exact dir name only |
| A4 | Delete other old claude temp session dirs (~40+ projects, nearly all 0.0 MB) | ~1.2 MB combined | per-dir `Remove-Item -Recurse -Force`, excluding `cdb03d59*` | Regenerable-class, dead sessions |
| A5 | Remove DEAD user PATH entry `C:\Users\haird\.vscode\extensions\anthropic.claude-code-2.1.222-win32-x64\resources\native-binary` (dir gone; installed ext is 2.1.247) | — | Edit HKCU:\Environment Path, remove that one segment; broadcast WM_SETTINGCHANGE | Reversible — removed string recorded here verbatim; re-append to restore. NOTE recurrence risk: version-pinned entry goes stale on every ext update |
| A6 | Remove DEAD machine PATH entry `C:\Program Files\Docker\Docker\resources\bin` (Docker deleted entirely 2026-08-11 by operator order) | — | Edit HKLM machine Path (admin), remove that segment | Reversible — string recorded here; re-append to restore |
| A7 | Set user env `PYTHONUTF8=1` (closes per-launcher coverage gap; scheduled-task blind spot is the payoff; absent at user/machine/process level per lens; no trailing-space variants present) | — | `setx PYTHONUTF8 1` | Reversible — `reg delete HKCU\Environment /v PYTHONUTF8 /f`. Zero risk to running processes (env read at process start; live runner untouched) |
| A8 | Prune stale repo-local git config branch sections (`branch.undefined.*`, `branch.claude/vscode-bridge-5548d1.*`, `stock-analysis-*` — vscode-merge-base droppings) | — | `git config --unset-all` per section / edit `.git/config` | Reversible — sections recorded by name here; zero behavior impact (cosmetic dedup) |

Not auto-applied despite looking like cache: live-tree `__pycache__` 37.8 MB / 24 dirs
and `.venv` `__pycache__` 117.2 MB / 614 dirs — 6 live .venv python/pythonw processes
running from the tree. IN-USE, never-touch. See §4.

## 2. INSTALL (serves a queued repo item)

**Zero INSTALL-NOW items.** The queue's tooling legs are already provisioned:
pytest-xdist 3.8.0 + execnet 2.1.2 (order-shuffle parallel half), pytest-cov 7.1.0 +
coverage 7.15.4 (coverage-gap report), git worktree (fresh-worktree CI leg, note E7
residue cleanup), stdlib (doc_cite_lint). VS Code: `charliermarsh.ruff` and
`tamasfe.even-better-toml` already installed — no extension gap.

Two INSTALL-AT-USE items (install only at the moment the backlog item is built, never
mid-queue — progress.md pins fresh suite counts, 4060/0/9 baseline):

| Item | Command (repo .venv interpreter) | Serves | Scoping (mandatory, same commit as install) |
|---|---|---|---|
| pytest-randomly | `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.venv\Scripts\python.exe -m pip install "pytest-randomly>=3.15,<4"` | Order-shuffle suite leg (it IS the leg) | **Opt-in only**: pin default-off in pyproject → `addopts = "--strict-markers -p no:randomly"`; leg opts in via `pytest tests/ -q -o addopts="--strict-markers" --randomly-seed=<recorded>`. HIGH risk unscoped: activates globally on install, shuffles order + reseeds random/numpy.random for every DoD run — repo already bitten by a global pytest plugin (SuperClaude, pyproject lines 12-36). `pip install --dry-run` first (transitive deps unresolved by lens); verify SuperClaude hook-ordering interaction with one shuffled run against the 4060-count corpus |
| pre-commit | same interpreter, `-m pip install "pre-commit>=4,<5"` then author `.pre-commit-config.yaml` then `pre-commit install` | Pre-commit-hooks backlog item | Install alone inert; value is the config (mirror DoD matrix: ruff/bandit/compileall). MEDIUM risk: writes `.git/hooks/pre-commit`, changes commit behavior for every session incl. automated fixers — defer until after PUSH CHECKPOINT 1 / queue drain. Hook envs land in `~/.cache/pre-commit` (disk, first-run latency) |

## 3. SIGN-OFF (operator-only) — action / benefit / risk-if-wrong, one line each

Scheduled tasks (CANDIDATE-DISABLE):
- Disable `\GCC` (GIGABYTE Control Center at-logon; never ran, result 267011) / logon decluttered / GCC won't auto-start, fan-RGB profiles may revert to firmware defaults.
- Disable `\StartAUEP` (AMD User Experience telemetry, Running) / telemetry off / AMD loses usage telemetry only; pairs with AUEPLauncher service.
- Disable `\Git for Windows Updater` (daily, last result 1) / one failing task gone / no auto-notice of new Git; manual `git update-git-for-windows` still works.
- Disable 4× `NvTmRep_CrashReport1-4` (NVIDIA crash-report telemetry) / telemetry off / NVIDIA loses crash uploads, drivers unaffected. Leave the rest of the NVIDIA update/profile set.
- Disable `\Apple\AppleSoftwareUpdate` (weekly, legacy iTunes stack) / dead-weight gone / no auto iTunes-iCloud updates; manual still possible.
- Disable 3× `\GoogleUserPEH\*` (Chrome promo/metrics helper) / dead-weight gone / nothing user-visible; Chrome updates unaffected.

Startup registry (CANDIDATE-DISABLE):
- Remove HKCU Run MicrosoftEdgeAutoLaunch / less logon load / Edge cold-starts slower, nothing else.
- Remove HKCU Run Grammarly `--autostart` / less logon load / overlay absent until manually launched.
- Remove WOW6432Node Run TeamsMachineInstaller (legacy classic Teams) / dead installer gone / classic Teams won't self-install for new users; new Teams unaffected.
- Remove WOW6432Node Run Adobe Creative Cloud + CCXProcess (if CC not daily) / logon load / CC apps and sync need manual launch.
- Remove WOW6432Node Run APSDaemon (Apple Push) / dead-weight / iTunes-iCloud push sync at boot lost.
- Remove WOW6432Node Run Spectrum (G.SKILL RAM RGB) / logon load / RAM RGB reverts to last-flashed pattern.

Services (CANDIDATE-DISABLE):
- Disable AUEPLauncher (AMD telemetry uploader) / telemetry off / AMD telemetry stops, drivers unaffected.
- Disable ESRV_SVC_QUEENCREEK + SystemUsageReportSvc_QUEENCREEK (Intel SUR telemetry — on a Ryzen box) / telemetry off / Intel DSA loses usage stats only.
- Disable IntelCollectorService + IntelTelemetryAgent / telemetry off / same blast radius as SUR.
- Disable DSAService + DSAUpdateService (Intel driver assistant on Ryzen; only relevant if Intel NIC/WiFi present) / two services gone / Intel component driver-update notices stop; manual updates still work.
- Disable PresentMonSharedService (frame-time capture) / one service gone / PresentMon-overlay FPS capture breaks if operator benchmarks games.
- Disable AdobeUpdateService (with the CC startup items) / one service gone / CC apps stop auto-updating.
- Disable Bonjour (Apple mDNS) / one service gone / AirPlay-iTunes discovery + some `.local` resolution lost — verify nothing on LAN relies on `.local` names FIRST.

INSTALLER-LEFTOVER deletions (Downloads, ~1,299 MB total, listed only per spec):
- Delete: VSCodeUserSetup-x64-current 226.8 MB (08-04), VSCodeUserSetup-x64-latest 199.5 MB (07-09), CursorUserSetup 188.8 MB (07-19), RX14-Setup 152.9 MB (07-17), Download_935586.msi 105.7 MB (02-02), 3× Forma Revit Add-In.msi 198.0 MB (08-15), SierraChartFileDownloader 9.6 MB, Intel-DSA 8.3 MB, Claude Setup 6.7 MB, tailscale 1.3 MB, Codex Installer 1.3 MB / ~1.3 GB back / risk: re-download if an installer is wanted again (all fetchable).

OPERATOR-CALL disk:
- `%TEMP%\WinGet\winlibs...gcc-16.1.0...zip` 260.2 MB — downloaded TODAY 2026-08-27 20:05, may be part of the active toolchain setup alongside the BuildTools install / 260 MB back / deleting mid-setup could strand a toolchain step. DECIDE AFTER BuildTools completes.
- `liquiditybot\sandbox_control_arm __pycache__` 10.0 MB / 12 dirs — regenerable, but sandbox-arm purpose unknown to the lens, no live process observed [I] / 10 MB / if the arm is dormant-but-armed, purge is still regenerable — low stakes, operator names intent.

Software uninstalls (census stale list — operator confirm use first):
- Anaconda3 2025.12-1 (dual with Python 3.14.0), Cursor 3.12.17 (unused vs VS Code), FreeCAD 1.1.3, LibreCAD, Any Video Converter, Kubernetes CLI/Helm, k6, games (CoD, VALORANT) / disk + update surface / each is a real uninstall — wrong call loses a tool the census had no usage evidence for either way.
- VS Code extension pruning: 59-63 installed; redundant markdown tools, duplicate Rust extensions, python-extension-pack, andrepimenta.claude-code-chat, sixth-ai / startup weight / reversible reinstalls, but outside every lens's mandate — operator picks.

Git core.autocrlf (system `C:/Program Files/Git/etc/gitconfig` has `core.autocrlf=true`):
- Flip to `input`/`false` at system scope / removes the machine-wide CRLF hazard named in the corpus-sync transport-bug memory / this repo is already protected by `.gitattributes` (`* text=auto eol=lf`, `*.bat text eol=crlf`) — changing the system default alters checkout behavior for EVERY other repo on the box without attributes; operator-only, and the memory's open item is the push_bundle zip path, not this working tree.

Smart App Control:
- No lens measured SAC state — no data, no recommendation. Restated plainly: **turning Smart App Control OFF is IRREVERSIBLE without a full Windows reinstall** (it can only go Evaluation→On/Off, never back On). Any action that would prompt to disable it is operator-only, eyes open.

Remote-ingress trust boundary (confirm, do not remove):
- VS Code Tunnel (HKCU Run `code-tunnel.exe`) AND Tailscale service are both standing remote paths to this always-on box / operator names which is the sanctioned remote path / removing the wrong one severs remote Claude Code/VS Code access to the box.
- Related posture note (report only): user-scope VS Code settings carry `claudeCode.allowDangerouslySkipPermissions: true` + `initialPermissionMode: "bypassPermissions"` — machine-global; operator should know.

Retired-vault decision (NEVER-TOUCH, docket only):
- Merge-or-retire of the 88 basenames unique to `C:\Users\haird\vaults\liquiditybot` remains an OPEN OPERATOR decision / closes the dual-vault ambiguity / a blind merge would overwrite canonical pages with stale variants and break its 0-broken-link wikilink graph — no fixer action of any kind.

## 4. NOT-RECOMMENDED (examined, rejected)

- Purging live-tree `__pycache__` (37.8 MB/24 dirs) or `.venv` `__pycache__` (117.2 MB/614 dirs) — 6 live .venv processes running from the tree; .venv is never-touch.
- Touching `%TEMP%\WinGet\vs_BuildTools.exe` (4.3 MB) or the HKLM RunOnce BuildTools resume key — would strand the in-progress install (never-touch).
- Removing Git `usr\bin` / `mingw64\bin` from machine PATH — dedup looks tidy but `usr\bin` exposes the unix toolset scripts may depend on; System32 still wins for `sort`/`find`/`bash`; verify consumers first, so not a plan item.
- Adding `Python314` base dir to PATH to "fix" the asymmetric `python`/`pip` resolution — repo work uses the .venv (canonical interpreter, memory-settled); could disturb the py-launcher workflow.
- Removing the QuickTime PATH entry — dir exists, harmless, contents unaudited.
- Disabling `\SoftLanding\*` tasks — OS-managed; Windows may recreate them, pure churn.
- Deduping duplicated git-lfs filter keys (system+global) — identical values, installed that way by design, benign.
- "Fixing" the `johnmason` Run-As on liquiditybot tasks — cosmetic rename artifact on never-touch tasks.
- py-spy (or any profiler) attached to the live runner pid — crosses the never-touch line on the live bot process; nothing queued needs it.
- Installing pytest-randomly or pre-commit NOW — both mutate global suite/commit behavior on install; deferred to INSTALL-AT-USE with scoping (§2).
- Reinstalling Docker Desktop — deleted 2026-08-11 by operator order; the PATH leftover is removed in A6, nothing else restored.
- Removing the VS Code Tunnel HKCU Run entry as startup clutter — it is plausibly the remote-access path; confirmation item in §3, never a cleanup.
- Any change to LLVM at `C:\Program Files\LLVM` — deliberately off PATH pending STL via BuildTools (never-touch).

## What this plan could not see (inherited lens blind spots)

Per-binary disk sizes for services; disabled/stopped non-MS services; scheduled-task
ENVs (PYTHONUTF8 absence matters most there — task definitions not opened, never-touch);
WinGet DiagOutputDir/windowssdk/Grammarly temp subdirs (30-38 MB each, unclassified);
Downloads scan was *.exe/*.msi only (no *.zip); WSL-side env; BuildTools "in progress"
inferred from task spec, not verified against a running installer process; transitive
deps of the two AT-USE installs (dry-run at use time); Smart App Control state
(unmeasured). Every lens enumeration returned rows — scans demonstrably ran ("0
findings" vs "scan broken" separated in favor of ran).
