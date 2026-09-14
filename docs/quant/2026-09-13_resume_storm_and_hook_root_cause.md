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

## 7. Activating the hook fix WITHOUT restarting the desktop app (21:30, verified)

Section 3's fix was correct and inert. Measured why [K]: the app's root
`claude.exe` processes were created 2026-09-13 18:41:04 local; the HKCU
`Environment` key's `LastWriteTimeUtc` and `Python314\python3.exe`'s
`CreationTimeUtc` are both 2026-09-14T01:44:49Z. The fix landed **63 min 45 s
after** the process tree existed, and Windows offers no supported way to mutate
a running process's environment block. The registry route can therefore never
reach this session's hooks. Its value is for the NEXT app launch.

**What actually reached them, with no restart and no config edit.** The hook's
shell is a non-login `bash -c` (all 12 `hooks.json` entries are
`bash "$CLAUDE_PLUGIN_ROOT/hooks/sg-python.sh" "<hook>.py"`). Its inherited
PATH, read from the raw process environment, orders
`...\Microsoft\WindowsApps` at **24** and `...\Python\Python314` at **34** —
the pre-fix order. But position **22** is `...\Local\Programs\Python\Launcher`,
which already exists, is already ahead of WindowsApps, and held only
`py.exe`, `pyw.exe` and `pyshellext.amd64.dll`. Copying `python3.exe` there
wins the lookup because **bash resolves PATH at exec time**: the environment
was never changed, only the filesystem at a location the existing PATH already
named. Nothing new was added to PATH, so no new precedence directory was
created — the alternative, `~/bin` at PATH position 3, would have introduced a
user-writable directory ahead of `system32` for every Git Bash process on this
box. Directory ACL checked: SYSTEM, Administrators and the user only.

**Mutation pair on the REAL hook command, real plugin root, synthetic Stop
event on stdin [K]:**

| arm | rc | stdout |
|---|---|---|
| without `Launcher\python3.exe` | 2 | the `[Errno 2]` of section 3, byte-identical to the live notifications |
| with it | 0 | `{"metrics": {"pv": 20008, "skipped": true, "skip_reason": 3, "fire_index": 1, "diff_strategy_v2": true}}` |

`skip_reason 3` is `not ENABLE_CODE_SECURITY_REVIEW or not HAS_API_CREDENTIALS`
at `security_reminder_hook.py:1974` — reached only after the hook loads,
parses the event, snapshots Stop state and enters its real review logic. An
earlier run of the same command returned `skip_reason -2`, which is a **stdin
JSON decode failure** at line 2275: the first synthetic payload was malformed
and PowerShell's pipe was in the path. That reading would have been mistaken
for a working hook. The instrument was the first suspect and it was the
instrument.

**The SDK step was not needed, contrary to the plan.** Running the SessionStart
hook through the same shim returned rc 0 and
`{"metrics": {"sdk_bootstrap": 1, "sdk_bootstrap_ms": 1013, "sdk_hook_py": 314}}`.
`ensure_agent_sdk.py` defines `NOOP_VENV = 1` — the venv at
`~/.claude/security/agent-sdk-venv` is already built and the SDK already
imports from it. A `pip install` into Python314's site-packages would have been
the wrong target entirely; the hook prepends that venv's site-packages itself.

**What this could not see.** The credential gate means no end-to-end LLM review
ran in the harness, only the load-parse-dispatch path. Whether a live hook has
credentials is not established here; the live evidence is the absence of new
`[Errno 2]` notifications after 21:30. Provenance for the copy is recorded in
`Launcher\python3.README.txt` — the file is installer-unowned and a Python
repair will remove it, silently re-breaking all 12 hooks.

## 8. Adversarial review of sections 5-7, and two errata (22:05)

Three hostile lenses over this session's own output. Both CRITICAL findings
are defects in the work above, and both are corrected here rather than argued
away.

### 8a. CRITICAL — the shim could not load its own runtime. REPLACED.

Section 7's fix placed a byte copy of `python.exe` in the Launcher directory.
**A copy of `python.exe` outside its install directory cannot find
`python314.dll` beside itself.** It started only because
`...\Programs\Python\Python314` happens to sit on PATH. Mutation, one variable:

| PATH | result |
|---|---|
| as shipped | rc 0, metrics |
| `Python314` entries stripped | **exit -1073741515 = `0xC0000135 STATUS_DLL_NOT_FOUND`** |

That failure is message-less, strictly worse than the readable `[Errno 2]` it
replaced, and section 7's own provenance note called the PATH entry
"redundant-but-harmless", which invites exactly the cleanup that triggers it.
The original fix put `python3.exe` BESIDE `python.exe` for precisely this
reason; relocating it for the precedence win silently traded that property
away, and section 7 did not re-check it.

**Replaced with a two-line `/bin/sh` script** named `python3` in the same
directory, which `exec`s the interpreter by absolute path. Verified on the
real hook command in both arms — rc 0 with a normal PATH, and **rc 0 again
with `Python314` stripped from PATH entirely**, the arm that killed the
binary. Two further gains: no 106 KB binary to drift out of version with the
interpreter it names, and an extensionless script is found by shells that
search PATH for exact names (the hooks' bash) and **not** by `cmd.exe` or
PowerShell, so the fix now reaches the one consumer that needed it and nothing
else. `Python314\python3.exe` stays — it sits beside its own DLL and is
self-contained. Provenance: `Launcher\python3.README.txt`.

### 8b. CRITICAL — a false verification claim shipped in a commit message.

Commit `c189c462` states: *"The four suites that read docs/ ... pass, 107
tests, rc 0."* **There are 32 such files, not four, and 675 tests, not 107.**
The four came from a `grep ... | head`, and the truncation was read as the
whole list — the sixth instance this session of an instrument answering
truthfully about a scope nobody asked about.

**The verdict is unchanged and the corrected run is green: 675 passed, 7
skipped, 1 xfailed, rc 0**, across all 32 files that reference `docs/`,
`HANDOFF` or `CODEBASE_TEMPLATE`. So nothing shipped broken. What shipped was
a claim narrower than its evidence, in the one place that outlives the code.
The history is pushed and is not being rewritten; this is the erratum.

A second instrument note from the same run: the first attempt returned **rc 1
with no failing test**. The cause was a pytest temp-directory teardown
(`PermissionError [WinError 5]` unlinking `pytest-current`), not a result.
`--basetemp` into the session scratchpad separates them. **An rc from a suite
is a claim about the harness until the summary line is read.**

### 8c. WARNING — 16 commits today were never security-reviewed, and will not be.

The plugin's own log (`~/.claude/security/log.txt`) has **no live hook
invocation before 20:31:48**, and that first entry is this session's manual
full-path probe, not a hook. `origin/main` took **18 commits on 2026-09-13**,
of which 16 landed before the fix — including `2dec30a3`, self-labelled
CRITICAL, and four guard/validator changes. The hook's state file now
baselines at `c189c462`, so the backlog is not covered retroactively and
nothing will ever review it. **The outage's real cost is that gap, not the
notification noise.** Remediation, if wanted, is a manual review over
`4d58ad61..3f891c19`; it is not done here.

### 8d. Lesser findings, recorded not fixed

- **`docs/CODEBASE_TEMPLATE.md` is named and located like canon.** It sits
  beside `ONBOARDING.md` and `INSTRUMENT_VERIFICATION_STANDARD.md`, and
  `tests/test_docs_era_currency.py` `rglob`s it into a gate's corpus. Its
  content carries zero refuter verdicts. The filename promises an authority
  the first paragraph disclaims, and the filename is what gets read.
- **Nothing detects the shim's loss.** The only signal is the notification
  storm returning.
- **Small, real increase in persistence surface.** `python3` for every Git
  Bash process now resolves to a user-writable file rather than a
  Microsoft-signed alias. The ACL is clean (SYSTEM / Administrators / user,
  inherited, no `Users` or `Everyone`) and **`system32` precedes it on PATH**
  (position 7 against 25), so no system binary is shadowed. Residual: anything
  already holding the user's token gets code execution on every Write, Edit,
  commit and push. Measured blast radius of the redirect itself is one
  consumer — `install.sh` probes bare `python3` as an existence check.

## 9. Red-team panel: 18 objections, and the one that inverts section 7 (23:05)

Five mandated-position panelists prosecuted this session's own claims, then
cross-examined each other. 37 objections raised, 2 withdrawn, **18 surviving**.
I re-derived the load-bearing ones myself before answering; the dispositions
below are mine and the measurements behind them are mine unless stated.

**Concession rate 14 full + 3 partial of 18.** That is the panel's own health
metric and it says this session was sloppy, not that the panel was generous.

### 9a. THE HEADLINE — the hook fix restored DETECTION, not REVIEW

**OBJ-3, BLOCKING. CONCEDED, and it inverts section 8c.** Section 8c said 16
commits went unreviewed. The truth is worse and is not bounded by today.

`HAS_API_CREDENTIALS` is `bool(ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN or
_HAS_3P_PROVIDER_AT_LOAD)` (`hooks/llm.py:124-126`), and all three review
entry points (`security_reminder_hook.py:1149`, `:1594`, `:1972`) bail on it.
The plugin's own log is unambiguous [K, read 23:00]:

    [21:40:00.214] Commit review: detected git commit in command
    [21:40:00.245] Commit review: LLM review disabled or no API credentials
    [21:44:52.058] / [21:44:52.098]   same pair
    [22:06:52.430] / [22:06:52.463]   same pair

Those three are **my own commits tonight, after the fix**. 39 `Stop hook: LLM
review disabled or no API credentials` lines say the same, the most recent at
22:52:57. `grep -i "vulns|findings|review complete|reviewed"` over the whole
log returns **0**, and `.git/sg-reviewed-shas` does not exist.

**No security review has ever completed on this box.** `git rev-list --count
origin/main` = **940**. The unreviewed set is 940, not 16.

And I had the evidence the whole time. I measured `skip_reason 3`, correctly
named it "the API-credential gate", wrote that the hook "loaded, parsed the
event and ran its Stop logic", and reported that as the hook WORKING. Both
statements were true. Their conjunction was false. **What I actually fixed was
the notification storm.** The right split is INVOCATION restored (real, mine,
verified) versus REVIEW never ran (pre-existing, untouched, and not fixable
without credentials in the hook's process environment).

### 9b. Section 7's shim broke PowerShell, and I said it could not

**OBJ-4, BLOCKING. CONCEDED, and MITIGATED.** Section 8a claimed the
extensionless script is "not found by cmd.exe or PowerShell". Measured, that
is false in both limbs:

| probe | result |
|---|---|
| `Get-Command python3 -All` | lists `Launcher\python3` **first**, ahead of the WindowsApps alias |
| `cmd /c "exit 7"` then `python3 --version` | no output, `$LASTEXITCODE` **still 7** |

`$LASTEXITCODE` retaining the previous native command's value is a false-green
generator: `python3 ...; if ($LASTEXITCODE -eq 0)` reads green on a call that
never ran. Before the shim, PowerShell's `python3` worked via the alias, so
this was a **regression I introduced while claiming the opposite**.

Mitigation applied and verified: `Launcher\python3.cmd` forwards to the same
interpreter. PowerShell now resolves the `.cmd` first and reports real exit
codes (measured 0 on success, **3** on `sys.exit(3)`, no longer the stale 7).
Git Bash still resolves the extensionless `python3`, and the real hook command
still returns rc 0. Both files are load-bearing; the README says so.

### 9c. The long-book row: premise stands, both consequences were wrong

**OBJ-1 / OBJ-5 / OBJ-17, CONCEDED.** "Every long-book partial close reports
realized P&L understated by 50 bps of closed notional" is **retracted**.
`TierAction.realized_pnl` has exactly **two** attribute reads repo-wide, both
tests (`tests/test_profit_tier_guards.py:85`, `tests/test_rev3.py:179`); the
value is constructed and discarded. `state.realized_pnl_total` is a different
attribute fed from fills, and `est_fee_bps` appears nowhere in `core/state.py`,
`execution/order_manager.py` or the capital layer. I published that clause in
five places under a "CONFIRMED four ways" banner that had verified only the
premise. **The banner covered the input and was read as covering the output.**

**OBJ-12 / OBJ-15 / OBJ-16, CONCEDED on substance, and independently
reproduced here.** "Fail-conservative, a wider buffer holds an exit open
longer and never tightens it" is false. Enumerating 960 states (entry 100,
long, tier_closed × high_water × price × sigma): **224 install a different
stop**. Stepping one tick turns that into a different EXIT in **6 of 8**
probes — at 101.0 with tier 1 closed the corrected engine arms a floor at
100.66 and exits on a tick to 100.65, while the shipped engine's floor sits at
101.66, **arms nothing**, and holds. The 80 bps figure does not hold a
protected position longer; it leaves the position **unprotected** through a
band the booked tier would have closed at break-even.

I contest OBJ-15's stronger form. "The installed long-book stop is IDENTICAL
at 80 and 30 in every reachable state" does not survive the enumeration above.
No invariant-5 issue either way: give-back, trail and the thesis stop are
untouched and no exit is *gated*; one protective floor fails to arm.

**OBJ-11, CONCEDED.** The same false sentence is in SHIPPED CODE, not only in
my write-up: `risk/profit_tiers.py:240-242` says "fail conservative … never
tighter … production never reaches this default at all", and
`core/config_guard.py:881-882` repeats the second half. The long book reaches
it. Both comments need correcting regardless of what happens to the value.

### 9d. The rest of the docket

| # | disposition | what I owe / did |
|---|---|---|
| OBJ-2 counts | **CONCEDE** | Re-derived two routes: **19** commits on 2026-09-13, not 18. `4d58ad61..3f891c19` = **15** and EXCLUDES the day's first commit; the inclusive range is `4d58ad61^..3f891c19` = **16**. My remediation range was off by one at the boundary that matters. "Four guard/validator changes" is 3 `fix(guard)` + 1 `fix(gates)`; state it that way or say 3. |
| OBJ-6 gc_pusher | **PARTIAL** | Mechanism upheld: `OVERFIT_REPORT_PATH` is a hardcoded `parents[1]/"outputs"` at `:1436`. But `grep -c LB_OUTPUTS scripts/gc_pusher.py` = **0**, so saying it "does not honour `LB_OUTPUTS`" implies a variable it was never offered. Correct phrasing: the path is hardcoded and no environment variable redirects it. |
| OBJ-7 measurement plane | **PARTIAL, with an instrument limit the objection did not name** | `gc_pusher.log` pushed `HTTP 200` every ~30 s straight through 19:50–19:59, and the supervisor relaunched the pusher from the stale tree at 19:56:40, so stale-tree metrics very likely reached Grafana. But **the log carries no date field and spans multiple days** (a second `19:50:08` appears 2,770 lines later), so no line in it can be attributed to a date without a second route. The objection's specific 19:54:20 / 19:57:57 stamps are not verifiable from this file, and neither is my "nothing was affected". Both claims are under-determined by this instrument. |
| OBJ-8 claim_check | **CONCEDE** | `scripts/claim_check.py` shipped at 15:51, **5 h 53 m** before the offending commit, and I did not run it. Its `_VOLATILE` nouns are `passed|failed|tests?|rows?|files?|mutants?|findings?|anchors?|panels?|trips?|entries` — so "107 **tests**" WOULD have been flagged, while "four **suites**" and "16 **commits**" would not. It is absent from CLAUDE.md's Definition of done (`grep -c claim_check CLAUDE.md` = 0). |
| OBJ-9 anchor | **CONCEDE, fixed** | `main.py:910` is the argument line; the construction is `:909-910`. The wrong anchor had propagated into `docs/HANDOFF.md` and an unamendable commit message. HANDOFF now reads `909-910`. |
| OBJ-10 dangling name | **CONCEDE, fixed** | The shim's line 3 named `python3.exe.README.txt`, which does not exist; the same dead name was committed at `:219` of this file. Both now read `python3.README.txt`. |
| OBJ-13 remedy is unfalsifiable | **DEFER** | Not independently verified. The claim is that `claim_check` default mode returned nonzero on 0 of the last 40 commits and that `--strict` is cleared by prose alone. If true it is a check that cannot fail, which is a catalogued class here. Owed: run the 40-commit sweep and a prose-injection probe. |
| OBJ-14 stale law in my own brief | **CONCEDE** | The panel brief I wrote corrected the template's ERA-4 to ERA-9 but left its `n=50` registration truncated; `CLAUDE.md` registers **n=50 lean AND n=100 verdict**. My correction paragraph fixed one error and copied another. |
| OBJ-18 citation range | **CONCEDE** | Plan item B1.25 cites `:243-244` for a claim that lives at `:241-242`; `:243-244` holds the EXPLICIT-0 note, which is correct and load-bearing. A mechanical editor executing B1.25 would delete the good note and leave the false claim standing. |

### 9e. What this section could not see

No credential was added and none should be added without the operator, so
"review never ran" is established but not remedied. The 940-commit backlog is
stated as a count of reachable commits on `origin/main`, not as a claim that
all 940 contain reviewable code. `gc_pusher.log`'s missing date field leaves
the storm-window metric question open by that route. OBJ-13 is undecided. And
this section is itself a self-review of a self-review, which is the posture
that produced every error above.

## 10. The credential question, settled — and a reviewer that needs no credential (23:45)

Section 9a established that the plugin's LLM review has never run because
`HAS_API_CREDENTIALS` is false. The operator has no API key and asked whether
anything could get them in, naming two candidates: a credential helper, and a
restart. **Neither works, and the reason is documented, not speculative.**

**A restart cannot help [K, official docs].** Claude Code injects a FIXED list
of variables into hook subprocesses — `CLAUDE_PROJECT_DIR`,
`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_EFFORT`,
`CLAUDE_CODE_REMOTE`, `CLAUDE_CODE_BRIDGE_SESSION_ID` — and no credential is on
it; the hooks reference says that if a hook needs API credentials you must set
them yourself. The authentication reference is more specific still:
`apiKeyHelper`, `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` apply to the CLI
and the surfaces wrapping it, and **Claude Desktop does not read these
environment variables at all — it uses OAuth.** This session runs in the
desktop app. So the subscription's own auth is structurally unavailable to a
hook subprocess, on any restart.

**No credential helper exists in this session** — the loadable tool set carries
nothing that brokers secrets through a password manager.

**The plugin's README is wrong on this point.** It lists "A working API path
(subscription, API key, or 3P provider config)", but the code requires
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or a 3P provider flag. Subscription
alone is not sufficient, and on Desktop it cannot become sufficient. That is an
upstream documentation defect worth reporting, not a local misconfiguration.

**What ships instead: `scripts/local_security_review.py` (SAFE).** It reviews a
diff with the Ollama model already installed on this box
(`qwen2.5:7b-instruct`, endpoint `127.0.0.1:11434`), so it needs no credential,
no subscription and no network egress. It reuses `scripts/local_llm_mcp.py`'s
client rather than growing a second one.

Its load-bearing property is the one this whole session was about: **a run that
could not happen never looks like a clean one.**

| exit | meaning |
|---|---|
| 0 | reviewed, nothing found |
| 1 | reviewed, findings reported |
| 2 | COULD NOT REVIEW — model unreachable, empty diff, unparseable reply |

`--self-test` plants a diff carrying a hardcoded live-format key, a
`shell=True` interpolation and an `eval()`, and FAILS unless the reviewer names
at least one. Measured: it names all three. **That is the difference between
"0 findings" and "the scan is broken", made mechanical.**

Two things the build measured that are worth keeping. A 7B model asked to
review a long diff **drifts into prose**; the first real run returned a commit
summary and the tool correctly refused to score it, so a single capped
corrective retry was added (capped on purpose — a loop that retries until
something parses would eventually accept a hallucination). And bandit's summary
block **rolls up confidence, not severity**: its "High: 1" was a Low-severity
B607 at high confidence, which is the exact misread CLAUDE.md's reading
discipline names. Resolved with the repo's existing `# nosec B603 B607`
convention for git plumbing, not with a new suppression.

Gates on the new files: 20 pins pass, ruff clean, bandit clean on the file and
on the full DoD scope, compileall clean. Ollama is already current (installed
0.34.0; latest release v0.34.0, 2026-09-05), so no update is pending there.

**Not claimed:** a 7B local model is not a frontier reviewer and will miss
things a larger one would catch. It is strictly better than the zero reviews
that have run on this box to date, and it is honest about when it did not run.
Whether it joins the Definition of done is an operator decision and was not
taken here.

## 11. Which local model — decided by measurement on this box (2026-09-14 00:30)

The operator asked which model best fits their hardware. Answered by running
both candidates over one corpus rather than by quoting benchmarks, because
published coding benchmarks measure code GENERATION and this task is
vulnerability DETECTION.

### 11a. The hardware is the constraint, and a live bot is part of it

| component | value |
|---|---|
| GPU | RTX 3070 Ti, **8 GB VRAM** |
| system RAM | 15.9 GB |
| CPU | Ryzen 5 5600X, 6 cores |
| free disk | 48 GB |

`Win32_VideoController.AdapterRAM` reports **4 GB** — the known 32-bit cap
artifact. The registry `HardwareInformation.qwMemorySize` reports **8 GB**,
which is the real figure. Reading the first number would have halved the
apparent ceiling. *Two routes, and they disagreed.*

8 GB is a hard ceiling here for a second reason: **this machine runs the live
runner.** A model that spills to system RAM competes with it on a 6-core CPU
with 16 GB, and a starved heartbeat makes the supervisor relaunch the bot from
the working tree. So "it runs if it offloads" is not acceptable, and dense
models above roughly 8B at q4 are out on that basis, not on quality.

### 11b. The harness: `scripts/local_review_eval.py` (SAFE)

14 cases — **9 planted defects** (hardcoded secret, command injection, eval on
untrusted input, SQL injection, unsafe pickle, path traversal, disabled TLS,
credential logged, swallowed auth error) and **5 controls**.

Three of the controls are the load-bearing ones: **SAFE look-alikes** — a
parameterised query, a list-form `subprocess.run`, and `ast.literal_eval`.
They contain all the dangerous vocabulary and are correct. **Recall alone is a
gameable metric**: a model answering "CRITICAL | everything" scores 100%. The
pins in `tests/test_local_review_eval.py` assert exactly that — the shouting
model must show 100% false positives and the silent model 0% recall — so the
score cannot be won by either degenerate strategy.

### 11c. The result, two identical runs at temperature 0

| model | recall | false pos | format | median |
|---|---|---|---|---|
| `qwen2.5:7b-instruct` (incumbent) | 8/9 | 2/5 | 10/14 | 0.5 s |
| **`qwen2.5-coder:7b`** | **9/9** | 2/5 | **14/14** | **0.3 s** |

Both 4.7 GB, same VRAM class, so the swap costs nothing. Better or equal on
every axis. **The most robust difference is the format column**, not recall:
14/14 means the prose-drift retry shim never fires, where the incumbent needed
it on 4 of 14. The recall difference is a single case (path traversal) and
should not be over-read at n=9.

**What the upgrade did NOT fix, stated because it is the interesting part.**
False positives are **tied at 2/5**, and both models flag the *same* two SAFE
look-alikes: the list-form `subprocess.run` and `ast.literal_eval`. Both got
the parameterised SQL right. So both are still partly matching vocabulary
rather than reading code, and a code-specialised model did not repair that.
Anyone reading this tool's output should expect false positives on correct
defensive code.

`DEFAULT_MODEL` in `scripts/local_security_review.py` now names the winner,
with the table in a comment beside it and a pointer to re-derive.

### 11d. What this could not establish

n=14 is a small corpus and every case is synthetic and short; real diffs are
longer and messier, and the one real diff reviewed so far returned NONE, which
is unfalsified rather than verified. The corpus was written by the same author
as the prompt, so it tests the pair, not the model alone. Only two models were
compared — a research pass over the wider library was still running when this
was written. And nothing here measures the thing that actually matters, which
is whether either model would catch a defect in this repo that a human missed.
