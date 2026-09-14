# 2026-09-13 — the resume storm, the supervisor that hot-reloaded onto stale code, and the hook that could not see its own file

SAFE class throughout: no order placement, fill, fee, universe, sizing or exit
logic touched. Two host-level changes (user PATH, a `python3.exe` copy) sit
outside the repo. Timestamps local (UTC−5) unless marked Z. Every number below
is as-of its stated read time; re-derive, never recall.

## 1. What the operator asked

Session `a8522b26` (main checkout), 19:55:43: *"had a stupid amount of sessions
to resume and they probably messed a ton of stuff up so check that."* That
session found and repaired the primary damage, then was killed at 19:58:53 with
its last two audit commands unanswered. This record completes the audit and
adds what the repair could not see.

## 2. Timeline [K] — reflog, `outputs/pc_supervisor.log`, `outputs/grafana_import.log`, process table

| local time | event | source |
|---|---|---|
| 19:50–19:53 | ~40 sessions resumed at once: 42 `claude` / 86 `node` processes, 28+80 started within 15 min | `Get-Process` at 19:58:26 |
| 19:53:17 | one resumed session ran `checkout: moving from main to claude/claude-rc-f3heik` in the MAIN checkout (148 behind, last touched 08-29). Working-tree config reverted to cut #8's 40/80 fees, `est_fee_bps` 80, `label_round_trip_cost_pct` 1.2, `watch_lane` absent | reflog; config diff by session a8522b26 |
| 19:53:40 | `pc_supervisor.py changed on disk -> restarting on the new code` — the supervisor hot-reloaded onto the TWO-WEEK-OLD supervisor (pid 34776); it then logged `dashboards changed + Grafana token present -> importing` (old boards pushed to Grafana Cloud) | pc_supervisor.log:8517 |
| 19:56:40 | old-code supervisor relaunched the metrics pusher from the stale tree | pc_supervisor.log |
| 19:57:29 | session a8522b26 `checkout: moving from claude/claude-rc-f3heik to main`; config read back 15/30, 0.45, `watch_lane` true, `dry_run` true | reflog; its transcript |
| 19:57:40–41 | supervisor hot-reloaded again onto current code (pid 34644, `IN a job … kill_on_job_close=True`); re-imported the current boards — `grafana_import.log`: command v58, learning v10, problems v19, alert-inputs v8, all OK | pc_supervisor.log:8522; grafana_import.log |
| 19:59:14 / 19:59:17 | auto-update check → `already up to date` | auto_update.log |
| 20:00:14 | new supervisor: `metrics pusher stale/absent -> relaunching` (the stale-tree pusher was gone; replacement runs current code) | pc_supervisor.log; process tree 20:09 |
| 20:08–20:12 | audit completed: main @ `78d88376` clean, 0 stashes, 15 commits on `origin/main` today all by the operator, control queue empty (raw and rtk-filtered reads agree), sentinels `force_dry.on` + `keepalive.on` + both locks present, no `.mutating` | this session |

**The runner never restarted.** `runner.lock` pid 14112 = `pythonw` started
09-12 18:27:50 (the `LiquidityBot` task's last run 18:27:32); `events.jsonl`
full-range grep shows the last boot lines at 09-12 18:28:39 / 18:29:38;
`status.json` was 2 s old at every read. That is why the 40/80 working-tree
config never reached the decision path: `STALE_SEC=120` never tripped. Luck,
not a guard — a `pytest` battery running concurrently (era-cut-procedure
item 7) would have made the supervisor relaunch the runner from the stale
tree. **Consequence still standing:** the running process holds the 09-12
code; today's 15 commits (incl. the guards-fail-open fixes `35cad93a`,
`05985214`, `2dec30a3`) are NOT live until an operator restart.

**Nothing else was touched.** Zero files changed after 19:50 in memory, the
vault, skills, `outputs/control/`, `outputs/reports/`; the 56 `docs/` and 3
`.claude/` mtimes are the two checkouts rewriting tracked files (tree matches
HEAD). All five scheduled tasks `Ready`, rc 0, S4U.

**Instrument note [K]:** resumed-session transcripts are re-persisted with
timestamps at resume time (dozens of sessions show first == last timestamp in
19:50–19:52Z+5). "Latest message" must be ranked by session activity, not by
transcript timestamp.

## 3. The hook error, root-caused (refuter-verified)

Every Stop / Write / Edit / `git commit` / `git push` / SessionStart in every
desktop-app session failed:

    C:\Users\haird\AppData\Local\Programs\Python\Python314\python.exe: can't open file
    'C:\Users\haird\AppData\Roaming\Claude\local-agent-mode-sessions\…\rpm\plugin_01YBNfaNwQztYsnUydt8m47G\hooks\security_reminder_hook.py': [Errno 2] No such file or directory

(plugin: Anthropic `security-guidance` 2.0.8). Two explanations were stated
and retracted in this session before the measurement settled it — recorded so
the shape is not repeated:

1. *"The sandbox hides the path"* — refuted: a full-path `python.exe` inside the
   same sandboxed Bash reads the file.
2. *"The MSIX alias runs python in a package context whose AppData redirect
   lacks the file"* — refuted by inode: `os.stat` of the Roaming path and of
   `AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\…`
   report the SAME file index; the PythonManager package's `LocalCache` is
   empty.

**Mechanism [K].** The Claude desktop app is an MSIX package
(`Claude_1.52386.6.0_x64__pzs8sxrjxfjjc`) with `FileSystemWriteVirtualization`
enabled. `AppData\Roaming\Claude` does not physically exist; it is an OVERLAY
that only descendants of `claude.exe` see (a WMI-spawned full-path python
sees `Roaming\Claude=False`). The plugin shim `sg-python.sh` probes
`python3.13..3.10` (absent) then `python3`, which resolves to
`%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe` — an app-execution alias
of `PythonSoftwareFoundation.PythonManager_26.3.240.0_x64__qbz5n2kfra8p0`
(zero managed runtimes). Its launcher spawns the classic
`Python314\python.exe` as a child WITHOUT the inherited overlay (no package
identity, same token, `IsProcessInJob=0`), so the child sees the real disk,
where the plugin root is absent. `py -3` (classic launcher, PATH entry 2)
sees the overlay but the shim never reaches it because the alias answers the
version probe.

**Mutation pair (synthetic Stop event on stdin):** alias → rc 2 + the ENOENT;
full path → rc 0 + `{"metrics": {"pv": 20008, "skipped": true, …}}`. PATH
reorder alone (no `python3.exe` anywhere but WindowsApps) → still rc 2 [K].

**Fix applied ~20:45 (host, user scope, reversible):** `Python314\python3.exe`
= byte copy of `python.exe` (106,328 B, hash equal); HKCU user Path gained
`…\Programs\Python\Python314` at position 4, immediately before
`…\Microsoft\WindowsApps` (5); prior value backed up in the session
scratchpad. Verified: with the new order, `command -v python3` →
`Python314/python3`, the shim exits 0 with the metrics JSON; the old order
still exits 2. Claude Code reads env at startup only → **the desktop app must
be restarted** before live hooks stop failing; that restart also runs the
plugin's SessionStart installer for `claude_agent_sdk` (never installed, same
cause). Dependents scanned: all five scheduled tasks and both Claude configs
use full interpreter paths; repo `.bat`/`install.sh` call bare `python` only
after `.venv` activation. Alternative not taken: disable the two PythonManager
aliases in Windows Settings (then the shim falls through to `python`/`py -3`).

## 4. Memory consolidation (outside the repo, `~/.claude/projects/…/memory/`)

42 → 27 topic files; 19 dated July-incident files retired to
`memory_retired_2026-09-13/` (nothing deleted) after their durable lessons were
folded into three themed files; four stale claims corrected against current
truth: `scripts/vscode_bridge.py` is NOT on main; global `core.autocrlf` is now
`false`; the bandit exclusion includes `./outputs`; and the security memory's
"execution_eligible is the Kraken-only gate" claim was rewritten to the
`main.py` deny-list (cut #10) per CLAUDE.md invariant 3. Two operator
directives recorded verbatim: *"do not let /caveman let you assume and get
results incorrect"* and *"… rtk … make sure everything that it glazes over
isn't incorrect either … do not assume."*

## 5. What this record could not see

Grafana Cloud state comes from `grafana_import.log`, not the API. Command
lines of S4U task processes are hidden to a non-elevated query (process tree
mapped by parent pid). The `outputs/control/` "empty" reading was confirmed
raw (PowerShell `-Force`) after rtk had filtered the first listing. The
fixed hook was exercised with a synthetic event, not by a real post-restart
Stop — the first restart is the live verification.

Re-derive: `git -C <main checkout> reflog --date=iso | head`, `grep -n
"restarting on the new code" outputs/pc_supervisor.log`, `tail
outputs/grafana_import.log`, `command -v python3` in Git Bash.

## 6. A red that was mine, not the tree's (gate-ordering in a fresh worktree)

The DoD battery run for this session reported **2 failed** in pytest:
`test_dashboard_no_value.py::test_every_map_key_names_a_real_exporter_family`
and `test_trading_dashboard.py::test_every_query_hits_an_emitted_metric`.
Both assert that every Grafana map key / panel query names a metric
`scripts/gc_pusher.py` can actually emit. Both failed naming the same family:
`liquiditybot_overfit_{rung_passed,passed,failed,armed,report_age_sec}`.

**Not a defect on `main` [K].** `gc_pusher` resolves its inputs from
`_REPO_ROOT = Path(__file__).resolve().parents[1]` (`scripts/gc_pusher.py:1092`)
— the tree the module lives in, hardcoded; it does NOT honour `LB_OUTPUTS`
(the same non-honouring that `cohort_eval.py` was fixed for on 09-04). This
worktree was created without an `outputs/` corpus, so the overfit family had
no source file and the contract tests correctly reported the keys as
unemittable. My battery ran gates in the order pytest → smoke → assurance →
overfit, so **pytest ran before the gate that creates the file it needs**:
worktree `outputs/overfit_report.md` is stamped **2026-09-13 20:58:45**, while
the pytest gate started 20:51:08 and ran 209 s (ended ~20:54:37).

**Three-arm re-run after the file existed — all green [K]**, 33 tests in both
files: serial with `LB_OUTPUTS` set (6.69 s), `-n auto` with it set (3.56 s),
serial with it unset (1.02 s). Parallelism is not the variable; the presence
of the generated artifact is.

**Consequence for anyone running the battery in a worktree:** a fresh worktree
has an empty `outputs/`, and several telemetry-contract tests read generated
artifacts through a repo-root path that no environment variable redirects.
Either run `scripts/overfit_check.py` before `pytest`, or run the battery in
the main checkout. This is the inverse of the vault's
`concepts/host-state-dependent-green` — a host-state-dependent RED — and the
battery's own summary could not have told you, because its exit-code column
was blank (a PowerShell `$args` parameter-shadowing bug in the harness, fixed
mid-session); the gate verdicts here were read from the logs, not from rc.
