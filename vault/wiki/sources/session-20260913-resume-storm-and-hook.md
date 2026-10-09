---
title: "Session 2026-09-13 (evening) — the resume storm, the hook that could not see its own file, and a red that was mine"
category: source
status: SETTLED
summary: "A ~40-session resume storm at 19:50 checked out a 148-commit-stale branch INSIDE the main checkout, reverting the working-tree config to cut #8's 40/80 fees; pc_supervisor then hot-reloaded onto that two-week-old code and pushed stale Grafana boards. The runner never restarted, so the stale config never reached the decision path — luck, not a guard: a concurrent pytest battery would have made the supervisor relaunch the bot from the stale tree. Separately, EVERY hook of the security-guidance plugin had been failing with [Errno 2] on its own file; two explanations were stated and RETRACTED before the measurement settled it. Real mechanism: AppData\\Roaming\\Claude is the packaged app's MSIX write-virtualization OVERLAY, visible only to descendants of claude.exe, and the python3 app-execution alias launches the interpreter as a child WITHOUT it. The host fix was correct and INERT — the process tree predated the registry write by 63 min 45 s — and was activated with NO RESTART by putting a python3 SHELL SCRIPT into a directory the hook shell's PATH already named, because bash resolves PATH at exec time (see §7 — the first attempt was a copied python.exe, which cannot find python314.dll and died message-less at STATUS_DLL_NOT_FOUND once Python314 left PATH; corrected the same session). Two pytest failures reported as inherited reds on main were DISPROVED and reclassified as my own gate-ordering artifact in a fresh worktree. Template-refactor phase 1 delivered an inventory whose refuter stage returned ZERO verdicts, so it is filed as candidates, not findings; its one claim re-derived four ways is that the LONG BOOK prices fees at the venue's zero-volume row (80 bps against the booked 30)."
tags: [hooks, msix, path-resolution, resume-storm, supervisor, gate-ordering, worktree, instrument-scope, long-book, fees, template-refactor]
sources: 1
updated: 2026-09-13
---

# Session 2026-09-13 (evening) — the resume storm, the hook, and a red that was mine

Raw: `raw/2026-09-13_resume_storm_hook_and_template_phase1.md`.
Repo record: `docs/quant/2026-09-13_resume_storm_and_hook_root_cause.md` (sections 1-8).
Repo state at filing: `main` = `c189c462`; bot pid 14112 RUNNING / DRY_RUN,
the original 09-12 18:27 boot, never restarted by any of this.

All timestamps local (UTC-5) unless marked Z. Every number is as-of its stated
read time. Re-derive, never recall.

---

## 1. The resume storm, and the guard that was not there

At 19:50-19:53 roughly forty sessions resumed at once (42 `claude` and 86
`node` processes; 28 and 80 of them started inside fifteen minutes). At
19:53:17 one of them ran `checkout: moving from main to claude/claude-rc-f3heik`
**in the main checkout** — a branch 148 commits behind, last touched 08-29. The
working-tree `config.json` reverted to cut #8's world: fees 40/80,
`est_fee_bps` 80, `label_round_trip_cost_pct` 1.2, `watch_lane` absent.

Twenty-three seconds later `pc_supervisor` logged
`pc_supervisor.py changed on disk -> restarting on the new code` and
hot-reloaded onto the two-week-old supervisor, which then saw its dashboards
"change" and pushed the stale boards to Grafana Cloud. A session repaired the
branch at 19:57:29 and the supervisor hot-reloaded back at 19:57:40.

**The runner never restarted, and that is the only reason the stale config
never reached the decision path.** `runner.lock` held pid 14112 throughout — a
`pythonw` started 09-12 18:27:50 — and `status.json` was never more than a few
seconds old, so `STALE_SEC=120` never tripped.

**This is luck, not a guard.** The supervisor relaunches the runner from the
WORKING TREE when the heartbeat goes stale, and a `pytest` battery run at
normal priority is already known to starve that heartbeat (era-cut-procedure
item 7). The storm and a battery on the same evening would have deployed
cut #8's fee configuration to the live bot. **The hazard is that a dev
checkout and the deploy checkout are the same directory**, so any session that
moves HEAD there is a deploy action whether it intends one or not.

Instrument note, and it changes how you find things: **resumed transcripts are
re-persisted with timestamps at resume time.** Dozens of sessions show
first == last timestamp inside a two-minute window. "The latest message" must
be ranked by session ACTIVITY, never by transcript timestamp.

## 2. The hook that could not see its own file

Every Stop, Write, Edit, `git commit`, `git push` and SessionStart in every
desktop-app session emitted:

    Python314\python.exe: can't open file '...\rpm\plugin_...\hooks\security_reminder_hook.py': [Errno 2]

surfacing as an endless stream of "security review found issues" notifications
carrying no findings.

**Two explanations were stated and retracted before the measurement settled
it**, recorded so the shape is not repeated. First, "the sandbox hides the
path" — refuted, because a full-path `python.exe` in the SAME sandboxed Bash
reads the file. Second, "the alias runs python in a package context whose
AppData redirect lacks the file" — refuted by inode: `os.stat` of the Roaming
path and of the package LocalCache path report the same NTFS file index, and
the PythonManager package's own LocalCache is empty.

**The mechanism.** The desktop app is an MSIX package with
`FileSystemWriteVirtualization` enabled. `AppData\Roaming\Claude` does not
physically exist; it is an **overlay visible only to processes descended from
`claude.exe`** — the view is process-tree-inherited, not token-based (a
WMI-spawned full-path python sees it as absent, with no package identity and
`IsProcessInJob=0`). The plugin shim probes `python3.13` down to `3.10`, all
absent, then `python3`, which resolves to a WindowsApps app-execution alias.
That alias's launcher spawns the classic interpreter as a **child without the
inherited overlay**, so the child sees the real disk, where the plugin root is
not there.

A correction to the shim's own account, worth keeping: **the shim does not
fall through.** Its version probe SUCCEEDS through the alias, printing 3.14, so
it `exec`s the alias and never reaches `python` or `py -3`. The shim's comments
predict a Store stub that "exits 49 silently"; on this box it does not. **The
failure is not interpreter selection, it is filesystem view** — which is why
the shim's own guard cannot save it.

## 3. The fix was correct and inert, and restarting was not the answer

The applied fix — a `python3.exe` byte copy beside Python314 plus a user-PATH
reorder putting Python314 ahead of WindowsApps — is right, and could not
possibly have worked on a running session. Measured: the app's root
`claude.exe` processes were created 18:41:04 local; the HKCU `Environment`
key's LastWriteTime and the new file's CreationTime are both
2026-09-14T01:44:49Z. **The fix landed 63 minutes 45 seconds after the process
tree existed**, and Windows has no supported way to mutate a running process's
environment block.

What reached the hooks changed no environment at all. The hook's non-login
`bash` already carried `...\Local\Programs\Python\Launcher` at **PATH position
22**, ahead of WindowsApps at 24 (Python314 sits at 34, behind both). Dropping
`python3.exe` there wins the lookup because **bash resolves PATH at exec
time** — the filesystem changed at a location the existing PATH already named.

Mutation pair on the REAL hook command with the real plugin root:

| arm | rc | stdout |
|---|---|---|
| without the file | 2 | the `[Errno 2]`, byte-identical to the live notifications |
| with it | 0 | `{"pv": 20008, "skipped": true, "skip_reason": 3, "fire_index": 1}` |

**`skip_reason` is the field that separates a working hook from a broken
one.** 3 is the API-credential gate, reached only after the hook loads, parses
the event and enters its Stop logic. An earlier run of the identical command
returned **-2, which is a stdin JSON decode failure** — a malformed synthetic
payload. Both print `rc 0, skipped: true`.

**The obvious variant was worse.** The same trick at `~/bin` (PATH position 3)
was empirically verified to work, and would have created a user-writable
directory ahead of `system32` for every Git Bash process on the box. The
Launcher directory already exists, is already ahead of WindowsApps, and its
ACL is SYSTEM / Administrators / user only, so **adding a file there creates no
new precedence surface**. A fix that works is not yet a fix that should ship.

**A planned step was refuted, not deferred.** The SessionStart hook run through
the same shim returns `sdk_bootstrap: 1`, and the installer defines
`NOOP_VENV = 1` — the venv at `~/.claude/security/agent-sdk-venv` was already
built and the SDK already imports from it. A `pip install` into Python314's
site-packages would have targeted the wrong place entirely.

## 4. A red that was mine, not the tree's

The session's DoD battery reported two pytest failures, both asserting that
every Grafana map key names a metric `scripts/gc_pusher.py` can emit, both
naming the `liquiditybot_overfit_*` family. They were reported as inherited
reds on `main`. **That was wrong and is disproved here.**

`gc_pusher` resolves its inputs from `Path(__file__).resolve().parents[1]` —
the tree the module lives in, hardcoded — and does **not** honour `LB_OUTPUTS`
(the same non-honouring `cohort_eval.py` was fixed for on 09-04). The worktree
was created with an empty `outputs/`, and the battery ran
pytest -> smoke -> assurance -> overfit, so **pytest ran before the gate that
creates the file it needs**: the worktree's `outputs/overfit_report.md` is
stamped 20:58:45 while the pytest gate ran 20:51:08 to roughly 20:54:37.

Three-arm re-run after the artifact existed: 33 tests green in all three arms
(serial with `LB_OUTPUTS` set 6.69 s, `-n auto` with it set 3.56 s, serial with
it unset 1.02 s). **Parallelism is not the variable; the presence of the
generated artifact is.** This is the inverse of
[[concepts/host-state-dependent-green]] — a host-state-dependent RED.

Two consequences. **Run `overfit_check.py` before `pytest` in a fresh
worktree, or run the battery in the main checkout.** And the battery's own
summary could not have told you, because its exit-code column was blank: a
PowerShell function parameter named `$args` shadowed the automatic variable, so
every gate ran with no arguments and "passed" in zero seconds. **The
implausible runtime, not the exit code, is what exposed it.**

## 5. Template refactor, phase 1 — filed as candidates, not findings

A 15-agent inventory produced `docs/CODEBASE_TEMPLATE.md` and
`docs/quant/2026-09-13_refactor_plan_phase1.md`: 93 files listed, 84 module
blocks, a DECISION/MIXED/MEASUREMENT/INFRA split of 30/12/18/24, 128 SAFE
candidates and 32 BOUNDARY items.

**Its refuter stage returned ZERO verdicts.** Standard check 1 is unmet on
every block, so each `[K]` is one agent's single read. The scripts census was
not delivered. strategies+regime arrived truncated at 4 of 13, so the entry
gate layer and every regime engine are UNREAD, not clean. main.py, runner.py,
api/ and sentiment/ were never inventoried. No test body was opened, so
"pinned by" means a test imports the module, not that any assertion fails on a
planted defect. **It is filed with those limits leading both documents.**

**The one claim re-derived by a second route, four ways, and CONFIRMED:**
`main.py:910` builds the long book's `ProfitTierEngine` from
`long_book.profit_taking` alone; that section carries no `est_fee_bps`; and
`risk/profit_tiers.py:245` falls back to `core.venue_fees.worst_row()[1]` =
**80.0**, Kraken's zero-volume taker row. Instantiating both engines from the
live `config.json` prints 30.0 for the 5 m book and **80.0** for the long book.
Consequence: the break-even ratchet at `:713` is `2*est_fee + be_buffer` =
**166 bps against 66**, both arming after tier 1; and `:393` books the same 80
against closed notional, so every long-book partial close reports realized P&L
understated by 50 bps of that notional.

**Direction, honestly: fail-conservative, not dangerous.** A wider buffer puts
the floor further above entry, holding an exit open longer and never
tightening it — exactly what the default is documented to be for. Long-book
tier 1 triggers at +8%, so by the time the ratchet arms the floor sits far
below market and may never bind. **Whether it has ever engaged is OWED.**

Also false and separately fixable: `core/config_guard.py:883` FATALs on an
absent `profit_taking.est_fee_bps` and comments that "production never reaches
ANY default". Its five dotted paths are all top-level;
`long_book.profit_taking.est_fee_bps` is not among them.
`tests/test_config_guard_long_book.py` pins assets, ladder, zones, TTL and
collars but has no fee case, so this was **missed, not excluded**. Nothing was
changed: fee booking and exit geometry are both cohort-resetting under era-9,
and it is on the HANDOFF docket.

## 6. What this session could not see

Grafana Cloud state was read from `grafana_import.log`, never the API. Command
lines of S4U scheduled-task processes are hidden from a non-elevated query, so
the process tree was mapped by parent pid. The `outputs/control/` "empty"
reading was confirmed raw with PowerShell `-Force` after rtk had filtered the
first listing. **The hook was exercised end-to-end only as far as its
credential gate** — no LLM review ran in the harness; the live evidence is the
absence of new `[Errno 2]` notifications across roughly fifteen
hook-triggering operations after 21:30, including two commits and two pushes.
The bot was verified by PID, not by "is it running" — a restarted bot would
also report RUNNING.

Related: [[concepts/the-method]] recurrences 17 and 18,
[[concepts/host-state-dependent-green]],
[[sources/session-20260913-guard-failopen-and-gauge]].

---

## 7. CORRECTION, same session (22:05) — the fix in §3 was fragile and has been replaced

Filed against this page's own interest, per the currency rule. An adversarial
review of §3 found a defect in it, and both sides are recorded.

**What §3 said.** The activation dropped a byte copy of `python.exe`, named
`python3.exe`, into the Launcher directory.

**What is wrong with it [K].** A copy of `python.exe` placed outside its
install directory **cannot find `python314.dll` beside itself**. It started
only because `...\Programs\Python\Python314` happens to sit on PATH. One
variable changed, measured both ways:

| PATH | result |
|---|---|
| as shipped | rc 0, metrics |
| `Python314` entries stripped | **exit -1073741515 = `0xC0000135 STATUS_DLL_NOT_FOUND`** |

That failure carries **no message at all**, which is strictly worse than the
readable `[Errno 2]` it replaced. The original fix had put `python3.exe`
BESIDE `python.exe` precisely so DLL resolution would hold; relocating it to
win the PATH race silently traded that property away, and §3 did not re-check
it. §3's provenance note compounded the hazard by calling the Python314 PATH
entry "redundant-but-harmless", which invites the exact cleanup that breaks it.

**What ships instead.** A two-line `/bin/sh` script named `python3` in the same
directory, which `exec`s the interpreter by **absolute path**. Verified on the
real hook command in both arms: rc 0 with a normal PATH, and **rc 0 again with
`Python314` stripped from PATH entirely** — the arm that killed the binary.
Two further gains: no binary to drift out of version with the interpreter it
names, and an extensionless script is found by shells that search PATH for
exact names (the hooks' bash) and **not** by `cmd.exe` or PowerShell, so the
redirect now reaches only the consumer that needed it.
`Python314\python3.exe` stays — it sits beside its own DLL and is
self-contained.

**§3's MECHANISM is unaffected and stands**: the overlay, the alias, the
registry fix's inertness, and PATH-resolution-at-exec-time are all unchanged.
What changed is the artifact placed at the winning PATH position.

**A second erratum from the same review.** The commit message on `c189c462`
claimed *"the four suites that read docs/ ... pass, 107 tests"*. There are
**32** such files and **675** tests; the four came from a `grep ... | head`
read as a complete list. The corrected run is green — 675 passed, 7 skipped,
1 xfailed, rc 0 — so nothing shipped broken, but the claim was narrower than
its evidence in the one place that outlives the code. **A sixth instance, in
one session, of `concepts/the-method` recurrence 17.**

**And the finding the review turned up that nobody was looking for.** The
plugin's own log has **no live hook invocation before 20:31:48**, and that
first entry is a manual probe. `origin/main` took **18 commits on 2026-09-13**
and **16 landed before the fix**, including one self-labelled CRITICAL and
four guard/validator changes. The hook's state file now baselines at
`c189c462`, so the backlog is never reviewed retroactively. **The outage's
real cost is that gap, not the notification noise.** Remediation would be a
manual pass over `4d58ad61..3f891c19`; it is OWED, not done.

---

## 8. SECOND CORRECTION (23:05) — a red-team panel inverted §2, §3 and §5

Filed against this page's own interest. Five mandated-position panelists
prosecuted this session's claims: 37 objections, 2 withdrawn, **18 surviving**,
**14 conceded outright and 3 in part**. The load-bearing ones were re-derived
by the author before answering. Full docket and dispositions:
`docs/quant/2026-09-13_resume_storm_and_hook_root_cause.md` §9.

### 8a. The hook fix restored DETECTION, not REVIEW — §2 and §3 read too well

**No security review has ever completed on this box [K].**
`HAS_API_CREDENTIALS = bool(ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN or
_HAS_3P_PROVIDER_AT_LOAD)` (`hooks/llm.py:124-126`) and all three review entry
points (`security_reminder_hook.py:1149`, `:1594`, `:1972`) bail on it. The
plugin's own log shows the author's OWN post-fix commits doing exactly that —
`Commit review: detected git commit in command` followed 31 ms later by
`Commit review: LLM review disabled or no API credentials`, three times
(21:40, 21:44, 22:06). Zero completed reviews in the whole log,
`.git/sg-reviewed-shas` absent, `git rev-list --count origin/main` = **940**.

**The author had this evidence and misread it.** `skip_reason 3` IS that
credential gate; it was named correctly, then described as "the hook loaded,
parsed the event and ran its Stop logic" and reported as the hook WORKING.
Both statements true, the conjunction false. **Split INVOCATION restored from
REVIEW ran** — a hook that executes and declines is not a hook that reviewed.
What was actually fixed is the notification storm.

### 8b. The shim broke PowerShell while the write-up claimed it could not

`Get-Command python3 -All` lists the extensionless script FIRST, ahead of the
WindowsApps alias, and the call emits nothing while leaving `$LASTEXITCODE` at
the PREVIOUS native command's value (measured: still 7 after `cmd /c "exit
7"`). That is a false-green generator, and a REGRESSION — PowerShell's
`python3` worked via the alias before. Mitigated and re-measured: a
`python3.cmd` beside it forwards to the same interpreter, PowerShell resolves
the `.cmd` first and now reports real codes (0, and 3 on `sys.exit(3)`); bash
still takes the extensionless script and the hook still returns rc 0.

### 8c. The long-book row: premise stands, BOTH consequences were wrong

**RETRACTED:** "every long-book partial close reports realized P&L understated
by 50 bps of closed notional". `TierAction.realized_pnl` has exactly TWO
attribute reads repo-wide, both tests; the value is constructed and discarded.
`state.realized_pnl_total` is a different attribute fed from fills, and
`est_fee_bps` appears nowhere in `core/state.py`, `execution/order_manager.py`
or the capital layer. The clause was published in five places under a
"CONFIRMED four ways" banner **that had verified only the premise** — the
banner covered the input and was read as covering the output.

**INVERTED:** "fail-conservative … holds an exit open longer and never tightens
it". Enumerated 960 states: **224 install a different stop**, and one tick
later that is a different EXIT in **6 of 8** probes — at 101.0 with tier 1
closed the corrected engine arms a floor at 100.66 and exits on a tick to
100.65, while the shipped engine's floor sits at 101.66, arms nothing, and
holds. The 80 bps figure leaves the position **UNPROTECTED** through a band the
booked tier would have closed at break-even. No invariant-5 issue: give-back,
trail and the thesis stop are untouched and no exit is *gated*; one protective
floor fails to arm. **The same false sentence is in SHIPPED CODE** at
`risk/profit_tiers.py:240-242` and half of it at `core/config_guard.py:881-882`.

### 8d. Smaller, all conceded

19 commits on 09-13, not 18; `4d58ad61..3f891c19` = 15 and EXCLUDES the day's
first commit (inclusive form `4d58ad61^..` = 16). `scripts/claim_check.py`
shipped **5 h 53 m** before the offending commit and was not run — and its
`_VOLATILE` nouns cover `tests` (so "107 tests" WOULD have been flagged) but
not `suites`, `commits`, `sessions` or `shas`; it is absent from CLAUDE.md's
Definition of done. The construction anchor is `main.py:909-910`, not `:910`,
and the wrong one had propagated into `docs/HANDOFF.md`. Plan item B1.25 cites
`:243-244` for a claim that lives at `:241-242`, so a mechanical editor would
delete a correct note and leave the false one.

**Instrument limit the panel did not name:** `outputs/gc_pusher.log` carries no
date field and spans multiple days, so no line in it can be attributed to a
date without a second route. Both the objection's "two forced deploy-exits at
19:54:20 / 19:57:57" and the author's "nothing was affected" are
under-determined by that file. What IS readable: it pushed `HTTP 200` every
~30 s straight through 19:50–19:59, and the supervisor relaunched the pusher
from the stale tree at 19:56:40.
