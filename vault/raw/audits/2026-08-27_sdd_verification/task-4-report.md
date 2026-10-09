# Task 4 report — verify unmerged branch `claude/remote-control-hds2hd` (tip 6f8b6315)

Verified from two independent, freshly-created worktrees (`git worktree add <dir> 6f8b6315`,
removed after use per Setup instructions). Main repo tracked tree was never edited/checked-out/reset.
Interpreter: `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.venv\Scripts\python.exe`.

**Branch-ref note**: the LOCAL ref `claude/remote-control-hds2hd` in the main repo is stale, tip
`69088a5d` — it is missing the final commit. The commit named in the brief, `6f8b6315`, exists
only on `remotes/origin/claude/remote-control-hds2hd`. I built worktrees from `6f8b6315` directly
(by SHA), matching the brief. Flagging this so nobody checks out the local branch name expecting
the tip commit.

---

## Q1 — SUITE STATE

Command: `<venv> -m pytest tests/ -q -rfE`, cwd = worktree root, full suite (no filters).

**Two independent fresh-worktree runs agree exactly** (double-derived per contract rule (e)):

| run | worktree | result | wall time |
|---|---|---|---|
| 1 | `scratchpad/hds2hd` (first checkout) | `2 failed, 4085 passed, 9 skipped, 1 error` | 540.06s |
| 2 | `scratchpad/hds2hd2` (second, independent checkout) | `2 failed, 4085 passed, 9 skipped, 1 error` | 568.43s |

Failing/erroring nodes, identical both runs:
```
FAILED tests/test_dashboard_no_value.py::test_every_map_key_names_a_real_exporter_family
FAILED tests/test_trading_dashboard.py::test_every_query_hits_an_emitted_metric
ERROR  tests/test_corpus_rotation_marker.py::test_tick_spawns_corpus_sync_immediately_on_marker
```
Skips (9, both runs): 8× `test_cpp_diode.py` (no g++/clang++ on PATH — expected, documented
skip reason in the test itself), 1× `test_pbo_variants.py:246` ("real Task 1 snapshot not present
in this checkout" — expected).

**A third, in-between run in a worktree I had already run several partial/bisection pytest
invocations against reported `4 failed, 4083 passed, 9 skipped`** — 2 more failures and 2 fewer
passes than the clean baseline. I could not re-capture that run's exact failing-node list (that
worktree was later removed) and could not reproduce it in either fresh worktree, so I do NOT
carry it as branch state — see "flakiness root cause" below for why I believe it was self-inflicted
worktree-state pollution from my own earlier bisection runs, not branch flakiness. Flagging as
**[UNKNOWN, not re-established]** rather than silently dropping it.

### Are the 3 reds the two HANDOFF "known settled" platform families?

HANDOFF.md RECENTLY SETTLED (line 203) names exactly two: `test_battery_gate.py` (cmd.exe pins,
`skipif(os.name != 'nt')`, so 0 skips/0 failures expected **on Windows, where they should run and
gate**) and `test_child_log_rotation.py` (NT rename-refusal platform split). **Neither test file
appears anywhere in the 3 reds above, and both families are fully green in both runs** (no
cmd.exe-related skip or failure appears in the skip/fail list at all, consistent with "unskipped
on Windows, where the battery gates"). **Answer: NO — these are a third, undocumented red family.**

### Are the 3 reds introduced by this branch's 22 commits, or inherited from main?

`git diff 5e785c16 6f8b6315 --stat` — none of the 31 changed files include
`tests/test_dashboard_no_value.py`, `tests/test_trading_dashboard.py`,
`tests/test_corpus_rotation_marker.py`, `scripts/gc_pusher.py`, `scripts/build_trading_dashboard.py`,
or `scripts/pc_supervisor.py`. Confirmed **byte-identical** (sha256) between the worktree and the
main repo for `scripts/gc_pusher.py`, `scripts/build_trading_dashboard.py`,
`tests/test_trading_dashboard.py`, `tests/test_dashboard_no_value.py`, `tests/conftest.py`.

Built a THIRD worktree at bare `5e785c16` (main tip, zero branch commits) and ran the same 3 tests:
```
FAILED tests/test_dashboard_no_value.py::test_every_map_key_names_a_real_exporter_family
FAILED tests/test_trading_dashboard.py::test_every_query_hits_an_emitted_metric
ERROR  tests/test_corpus_rotation_marker.py::test_tick_spawns_corpus_sync_immediately_on_marker
2 failed, 1 passed, 1 error in 0.85s
```
**Identical failure shape on bare main.** These are pre-existing, main-inherited defects — the
branch under test did not introduce them. **[K] read + [K] run, two routes (worktree diff +
independent bare-main run), both agree.**

### Root cause of each (asked the runtime, not read-and-guessed)

**1–2. Veto dashboard tests** — `_aux_emitted()` (`tests/test_trading_dashboard.py:301`, shared by
both failing tests) rebinds `RETRAIN_HISTORY_PATH`/`MODEL_REGISTRY_PATH`/`COHORT_SCRIPT`/
`_cohort_cache` to throwaway fixtures, but does **not** rebind `gc_pusher.VETO_SCRIPT` /
`_veto_cache`. `_veto_quality_metrics()` → `_run_veto_quality()`
(`scripts/gc_pusher.py:1246-1283`) shells out for real: `subprocess.run([sys.executable,
VETO_SCRIPT, "--json"], cwd=str(_REPO_ROOT), ...)` where `VETO_SCRIPT =
scripts/gate_efficacy_report.py` and `_REPO_ROOT` resolves to whichever checkout is running. On a
fresh checkout with no accumulated gate/audit history, `gate_efficacy_report.py --json` has
nothing to compute a baseline band from → `_run_veto_quality` returns `None` → zero
`liquiditybot_veto_*` metrics get emitted → both contract tests (map-key coverage, panel-query
coverage) fail on the missing family. The live main repo happened to pass earlier in this session
only because it has a long-running bot's real audit history on disk for `gate_efficacy_report.py`
to read — that is host-state, not code, and is not something a fresh checkout (or CI) has. This
traces to main's own most recent commit, `5e785c16` "feat(telemetry): the veto counters learn
whether the vetoes were right" — its test fixture never grew a rebind for the new veto subprocess
path.

**3. corpus_rotation_marker ERROR** — `scripts/pc_supervisor.py:104`: `_VAULT_GUARD_STAMP = OUT /
".vault_guard_stamp"` is a module-level path **not present** in `tests/conftest.py`'s
`_REDIRECTED_PATH_ATTRS` registration tuple (line ~99-103), unlike its sibling stamps
(`_UPDATE_STAMP`, `_CORPUS_SYNC_STAMP`, `_CORPUS_ROTATION_MARKER`, etc., which are all listed).
`test_tick_spawns_corpus_sync_immediately_on_marker` calls the real `sup.tick()`, which (via
`_stamp_due(_VAULT_GUARD_STAMP, VAULT_GUARD_SEC)`, `pc_supervisor.py:848`) writes a fresh
`outputs/.vault_guard_stamp` under the checkout's own tree whenever that file doesn't exist yet or
is stale — caught, correctly, by `conftest.py`'s own `_no_production_outputs_writes` safety net.
Confirmed the mechanism directly: `outputs/.vault_guard_stamp` already existed in the live main
repo (stamped 2026-08-27 15:49 by the running bot) at the time I ran the isolated 3-test check
there, so `_stamp_due` was not due and no write happened — hence no violation there. In a fresh
worktree the file is absent, the write fires, and the test fails. **This is the same leak-class
pattern this very branch's own commit `3ec6dbbc` fixed for a different constant** ("`
ml.postmortem.paths_path` joins the canonical redirect list (9th leak-class instance)") — `
_VAULT_GUARD_STAMP` is an unregistered 10th instance, added on main's own recent security work
(`4b49322f`/`f254b110`, "vault guard"), never touched by this branch, never caught by
`3ec6dbbc`'s fix because that fix targeted a different attribute name.

**Both defects are pre-existing on main `5e785c16`, undocumented in HANDOFF's RECENTLY SETTLED
table as of `6f8b6315`, and were not introduced by any of this branch's 22 commits.** Given the
repo's own "no orphan claims" rule, this is now itself an owed finding — not something to fold
silently into "the branch is fine."

### Flakiness root cause (secondary finding, [I] inferred, not fully re-derived)

The single anomalous "4 failed, 4083 passed" reading came from a worktree in which I had already
run many *partial* pytest invocations (single files, subsets) while bisecting the veto-dashboard
failure. `outputs/.vault_guard_stamp` and possibly other un-redirected sidecar state accumulate
**on disk, across pytest invocations, inside the SAME worktree**, because the guard that would
normally catch such a write only *fails the test*, it does not *revert the write*. A later full run
in that same dirtied worktree can therefore see a different world than a pristine one. Both
timed fresh-worktree runs (the ones I'm reporting as authoritative) agree with each other and with
a from-scratch bare-main check, so I trust `2 failed, 4085 passed, 9 skipped, 1 error` as the
number; the "4 failed" reading is attributed to self-inflicted worktree pollution from my own
bisection, not evidence of branch-level nondeterminism — but I did not fully re-derive which 2
extra tests it was, so flagging this attribution as inferred, not proven.

---

## Q2 — MERGE STATE

`git merge-base 6f8b6315 5e785c16` → `5e785c16` itself. **Main tip 5e785c16 is already a direct
ancestor of the branch tip** (`git merge-base --is-ancestor 5e785c16 6f8b6315` → true). The branch
is a pure linear descendant: `main + 22 commits` (`git rev-list --count`: 725 branch vs 703 main).

`git merge-tree --write-tree 5e785c16 6f8b6315` → single tree SHA `ec36f6d0…`, no conflict
markers. Confirmed this equals the branch's own tree exactly: `git rev-parse 6f8b6315^{tree}` →
same `ec36f6d0…`. **This proves the merge is a trivial fast-forward — merging changes nothing
beyond what the branch already contains. Zero conflicts, by construction, not just by absence of
markers.**

---

## Q3 — TRIALS-1 "absent-is-not-zero" (asked the runtime)

Ran `scripts/trial_ledger.py` and `scripts/overfit_check.resolve_dsr_trials` live against
constructed temp ledgers (script: `scratchpad/q3q4/probe.py`, `probe2.py`).

**(a) Missing/empty ledger:**
- `read_ledger()` on a nonexistent path: raises `FileNotFoundError` — loud, never silently `[]`/0.
- `trial_ledger.py` CLI (`main()`) on a missing ledger: prints `"no ledger at {p} (ABSENT, not
  zero trials)"`, `rc=0` — names the absence explicitly, never claims N=0.
- `harvest()` on an outputs dir with neither `tune_search_state.json` nor `sweeps/*.csv`: those two
  dynamic sources correctly land in the `absent` list (`['tune_search_state.json',
  'sweeps/*.csv']`), **not** as zero-count rows. Static sources
  (`geometry_search_grid`=48, `of3_model_space`=9, derived from code constants, not files) are
  still correctly counted since their presence doesn't depend on a file existing.
- **The DSR-facing entrypoint**, `resolve_dsr_trials(configured=50, ledger_path=<missing>)`:
  returns `(50, "OF-5 trials: assumed N=50 (no ledger at ...; var=SR^2 fallback)")` — absence
  falls back to the pre-registered `configured` floor and **says so in the line that gets
  printed**, never returns N=0 or N=1.

**(b) Populated temp ledger:** wrote 2 distinct `battery` strategy rows + 1 `harvest` row with
`count=17` via `append_rows`; `measured_trials(read_ledger(...))` → `{'n_trials': 19,
'by_source': {'battery': 2, 'harvest': 1}, 'degenerate': 0, 'non_degenerate': 3}` — correct
(2 distinct battery configs + 17 harvested = 19).

**Verdict: absent-is-not-zero confirmed on the running code at every layer (raw reader, CLI, and
the actual OF-5 entrypoint), not just by reading the source.**

---

## Q4 — OF-5 RATCHET mutation test (asked the runtime)

Target: `resolve_dsr_trials(configured, ledger_path)` in `scripts/overfit_check.py:622`.

- Built ledger A (25 distinct battery strategy_ids, measured N=25). `resolve_dsr_trials(configured=10,
  ledger_path=A)` → `n_trials_eff=25` ("measured N=25 from ledger... ratchet deepens").
- Built ledger B (24 distinct battery strategy_ids, measured N=24, a *separate* smaller ledger).
  `resolve_dsr_trials(configured=25, ledger_path=B)` → `n_trials_eff=25`
  ("measured N=24 < configured; ratchet holds configured 25"). **The smaller re-measurement did
  NOT relax the ratchet below 25 — confirmed by mutation, not by reading the code.**

**Important nuance, established by further probing** (not a defect, but worth stating precisely
since the brief's phrasing ("feed it N=k, then N=k-1") could be read as claiming persistent
cross-run memory): `resolve_dsr_trials` is a **pure function with no cross-call state**. The
"never relaxes" guarantee holds *relative to `configured`*, which in the real caller
(`scripts/overfit_check.py:1033-1039`) is always sourced fresh from `config.json`'s
`ml.overfit.dsr_n_trials` (default 7) — a **stable, human-edited, config-guard-bounded floor**, not
a "best N ever measured." I confirmed this directly: calling
`resolve_dsr_trials(configured=10, ledger_path=B)` (24-row ledger) after having already seen a
25-measurement in a prior call returns `n=24`, because nothing outside the ledger persists between
calls. This is coherent with the branch's own docstring ("never relax it below the **configured**
floor") — the ratchet's anchor is the config value, not run history, and the config value is not
something that regresses on its own. **Not a defect; documenting so nobody later mistakes this for
a persistence guarantee it doesn't make.**

---

## Q5 — OF-3 `_BASE_ORDER` shadow (ebbab4e2)

The "shadow" was a local re-declaration of `_BASE_ORDER` inside `model_space_pbo()`
(`ml/overfit.py`), pre-existing since commit `c8efc063` (2026-07-26 07:43:50 UTC) — long before
this branch. The **module-level** `_BASE_ORDER` constant that `ebbab4e2` says "the module reads
now" did not exist until **this same branch's own commit `d1184dad`** (2026-08-27 18:30:15 UTC,
"feat(trials): harvest mode"), which added it purely so `trial_ledger.harvest()` could `from
ml.overfit import _BASE_ORDER; len(_BASE_ORDER)` for the `of3_model_space` count. `ebbab4e2`
(2026-08-27 18:41:56 UTC) removed the now-redundant local copy **11 minutes 41 seconds later, same
session**.

Diffed both declarations at `d1184dad` — **byte-identical tuple content**, both
`("logistic", "gbt_d2_lr05", "gbt_d2_lr10", "gbt_d3_lr05", "gbt_d3_lr10", "gbt_d4_lr05", "gbt_mono",
"mlp_small", "adaptive_gbt")`, differing only in indentation whitespace. Since Python's local-scope
shadowing means `model_space_pbo()` used whichever tuple was in scope, and both were identical,
**`model_space_pbo()`'s actual computed output was never affected**, not even during the 11-minute
window.

Searched `docs/quant/` and the vault (`C:\Users\haird\Documents\liquiditybot\vault`) for
`model_space_pbo` — found in `docs/quant/2026-07-26_phase3_adjudication.md`,
`docs/quant/pbo_admission_policy.md`, and their vault mirrors. **All dated 2026-07-26** — over a
month before the module-level constant (and hence any possibility of shadow-vs-module divergence)
ever existed. **No published PBO numbers anywhere overlap the shadow's existence window; none need
re-derivation.**

---

## Q6 — MORATORIUM CLASS: f40d298c and 550e9011

`git diff 5e785c16 6f8b6315 --stat -- core/state.py main.py runner.py execution/ risk/` →
**empty output**. Zero bytes touched in the live decision path, order lifecycle, fill simulator, or
fee-booking implementation across the *entire* 22-commit branch, not just these two commits.

**f40d298c** (`scripts/replay.py` +17/-2, `tests/test_replay_mutate_hook.py` new file):
- Adds an optional `mutate_bot=None` kwarg to `run_replay()`. Default path asserted
  byte-identical to pre-hook behavior by `determinism_ok(a, b, keys=...)` comparing a call that
  omits the kwarg entirely against one passing `mutate_bot=None` — **ran this test directly, it
  passes** (`2 passed in 6.62s`).
- `scripts/replay.py` is exclusively a measurement/offline-replay tool. Grepped every caller of
  `run_replay`/`scripts.replay` across the branch tree: `core/replay_gate.py`,
  `scripts/archetype_battery.py`, `scripts/overfit_check.py`, `scripts/replay_gate.py`,
  `scripts/smoke_test.py`, `scripts/sweep.py`, and tests only. **`main.py` and `runner.py` never
  call it.**
- **Verdict: SAFE.** Confined to an offline-replay harness that only ever drives the engine over a
  *recorded* session for measurement purposes; never reachable from the live runner loop.

**550e9011** (`scripts/archetype_battery.py`, `scripts/replay.py` +1, 2 test files):
- `scripts/replay.py`: adds `"entry_fees": round(bot.state.entry_fees_total, 2)` to the summary
  dict `run_replay()` returns — **reads** an existing `core/state.py` field
  (`entry_fees_total`, unchanged) into a report output; does not touch how that field is
  accumulated.
- `scripts/archetype_battery.py`: fixes the battery's own local `net_pct`/`gross_pct` CSV-row
  computation for the "deployed" ledger member to **match** the pre-existing, unchanged
  `core/state.PortfolioState.realized_net_all_in()` convention (`realized_pnl_total -
  entry_fees_total`, confirmed present unchanged at `core/state.py:217-222`) — this is a
  measurement-tool bug fix bringing a *report-only* CSV column in line with an accounting method
  that itself was not touched. Also redirects `ml.postmortem.paths_path` to the battery's own
  throwaway `out_dir` (QA isolation, same leak-class as above, fixed locally here) and scopes the
  no-factory "deployed" member to the two pre-registered harness profiles only.
- **Verdict: SAFE.** "Ledger rows" in the commit title means the `trial_ledger.csv` measurement
  artifact, not any production accounting ledger; `core/state.py` is untouched (confirmed above).

**Both commits: SAFE as shipped, confirmed by direct diff (not inference) that the live decision
path, sizing, stop/exit geometry, fill simulator, fee-booking, and order lifecycle files carry zero
changes across the whole branch.**

---

## Q7 — SEV-1 tape defect, second-route verification (e4c1469b) — injection-tested

Spec doc `docs/superpowers/specs/2026-08-27-archetype-null-battery-design.md` (amended by
`e4c1469b`) describes the pre-fix defect: the old `smoke_test.py` mock froze candle `time` at
`0..119` on every `get_market_data` call (history clock never advances), returned a byte-identical
normalized candle series per call (deterministic per-call reseed), while a separate `prices` dict
drifted independently — tripping the engine's watchdog on the resulting divergence.

The fix (`b367e65c`) is a **rebuilt, self-contained tape generator** (`PriceWorld` +
`_WorldVenue` classes in `scripts/archetype_battery.py`) plus a **self-check function**,
`tape_coherence(recording_path)` (line 237), which measures three properties directly off a
recorded tape: `bar_times_advance` (candle end-times strictly increasing across frames),
`distinct_series` (count of distinct rounded closes seen — catches frozen/constant series), and
`max_venue_gap_bps` (divergence between okx candle close and the nearest-by-file-position kraken
tick).

**Confirmed the fix works on the real generator**: ran
`tests/test_archetype_battery.py::test_tape_bar_times_advance_and_series_evolves` directly against
the actual `record_tape()` output — `1 passed`. This alone is weak evidence (a check that reads
correct on a good input proves little); did the required injection test.

**Injection test** (`scratchpad/q7/inject_defect.py`): hand-built two synthetic JSONL recordings
reproducing the exact defect shape from the spec, and called `tape_coherence()` on them directly:
1. Frozen bar times (`time=0..119` on every frame) + byte-identical `close` on every frame →
   `tape_coherence()` returned `{'bar_times_advance': False, 'distinct_series': 1,
   'max_venue_gap_bps': 0.0}`. **Self-check correctly fires** (`bar_times_advance is False`,
   `distinct_series == 1`, exactly the "frozen-mock failure mode" the real test's docstring names).
2. Same frozen candle history, but kraken tick price drifting +1%/cycle (the second sub-defect:
   prices dict drifts while candle history doesn't) → `max_venue_gap_bps: 485.3`, far past the
   `<50.0` threshold the real pin (`test_tape_bar_times_advance_and_series_evolves`) asserts.
   **Self-check correctly fires on this sub-defect too.**

**Verdict: the coherence self-check is not vacuous — proven by injection, both sub-defects, not
just by the positive-path test passing.**

**Scope note (not a defect):** `tape_coherence()` is invoked **only from
`tests/test_archetype_battery.py`** — grepped `scripts/archetype_battery.py`'s own `run_battery()`
and found no call site there. It is a CI-time pin, not a runtime gate inside a live battery
invocation; a future regression would be caught by the DoD test-suite gate, not by
`archetype_battery.py` refusing to run on a bad tape at the time someone runs it by hand. Worth
knowing if anyone later runs the battery standalone outside CI.

---

## Summary verdict

The branch (`claude/remote-control-hds2hd` @ `6f8b6315`) is:
- A clean fast-forward of main @ `5e785c16` — zero merge conflicts, mathematically guaranteed
  (merge-tree output tree == branch's own tree).
- SAFE-class as shipped for the two commits scrutinized under the moratorium (f40d298c, 550e9011)
  — confirmed by an empty diff across the entire branch for every live-path file
  (`core/state.py`, `main.py`, `runner.py`, `execution/`, `risk/`).
- TRIALS-1's "absent-is-not-zero" and OF-5's ratchet-never-relaxes-below-configured-floor claims
  both hold under direct runtime testing (not just reading).
- The OF-3 `_BASE_ORDER` shadow was a real but functionally inert same-session artifact (11
  minutes, byte-identical content, unmerged, nothing published during its existence) — no
  re-derivation owed.
- The SEV-1 tape-defect self-check is empirically non-vacuous (fires correctly on both injected
  sub-defect shapes).
- **The full suite is NOT clean**: 2 failed + 1 error, reproduced identically across two
  independent fresh worktrees of the branch tip AND on bare main @ `5e785c16` with zero branch
  commits applied. These are **not** the two HANDOFF-documented platform-skip families and are
  **not introduced by this branch** — they are pre-existing, currently-undocumented defects in
  main's own most recent commit (`5e785c16`, veto-counter telemetry) plus a 10th instance of a
  leak-class this same branch partially fixed elsewhere. Root cause identified for both via direct
  code tracing and (for the vault-guard one) direct mechanism confirmation against live-repo state.
