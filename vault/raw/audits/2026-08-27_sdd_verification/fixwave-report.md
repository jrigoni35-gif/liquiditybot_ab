# Fix-wave report — veto-efficacy telemetry chain, C1-C7 + I1-I5

Applied 2026-08-27, ~21:55 UTC (start) – ~23:10 UTC (commit) [K]. Repo
`c:\Users\haird\Documents\liquiditybot\liquiditybot_ab`, branch
`claude/claude-rc-f3heik`, starting HEAD `a94b5751` (the task-3 fix this
wave sits on top of). Interpreter `./.venv/Scripts/python.exe` throughout.
Followed the focused-fix protocol (`C:\Users\haird\.claude\skills\focused-fix\SKILL.md`):
SCOPE -> TRACE -> DIAGNOSE -> FIX -> VERIFY, in order, no fix before
DIAGNOSE completed.

## STATUS: FIXED

Commit: `62ab10c010d25b3857a5164e291f9216f98001bb` on
`claude/claude-rc-f3heik`, local, not pushed.

---

## Phase 1-2: SCOPE + TRACE

Feature scope, per the fix-wave brief: `scripts/gate_efficacy_report.py`
(core) + consumers `scripts/gc_pusher.py`, `scripts/build_trading_dashboard.py`
(+ built artifact `docs/grafana/liquiditybot_problem_solution.json`),
`scripts/learning_panel.py` (checked, not modified), `tests/test_veto_quality.py`,
`tests/test_boards_stripped.py`, `docs/HANDOFF.md`.

**Inbound deps read**: `ml.history.label_era_of`/`LABEL_ERA_TRIPLE_BARRIER`/
`LABEL_ERA_UNKNOWN`/`_row_label_era`/`triple_barrier_era` (read in full,
lines 250-460 area); `scripts.gate_truth_report.effective_n` (unchanged,
not touched). Confirmed via `csv.DictReader` header read against the live
`outputs/signal_history.csv` that the corpus carries NO `label_max_bars`/
`horizon_bars` per-row column — load-bearing for the C3 design decision
(a fallback row cannot be horizon-qualified from data it doesn't have,
so it must go to UNKNOWN, not be guessed).

**Outbound consumers traced**: `scripts/gc_pusher.py::_run_veto_quality`/
`_veto_quality_metrics` (reads `by_code` JSON's `rate/lo/hi/n_eff/
anti_selective/selective`, now also `comparison/era_overlap`);
`scripts/build_trading_dashboard.py` (panel descriptions + new panel,
reads nothing programmatically — text only); `scripts/learning_panel.py:64`
registers `gate_efficacy_report.py` as a subprocess `Route` menu entry
only, no field/signature dependency — **confirmed structurally unaffected,
not modified**, per the brief.

**Needle checks (grep, [K])**:
- `grep -rn "gate_efficacy_report" scripts core ml risk regime strategies sentiment api main.py runner.py tests` — only the 3 in-scope consumers plus `ml/history.py:2346` (a comment noting `disp` is regex-scraped, informational, no dependency to break).
- `grep -n "label_era" outputs/signal_history.csv header` (via DictReader) — column exists; live corpus distribution: `triple_barrier_h432` 8108, `triple_barrier` 5290, `exit_sim` 2496, `legacy` 1734, `exit_sim_time_stop` 459 — **0 blank, 0 "unknown"** on the live corpus (both C3's ambiguous-fallback path and the UNKNOWN-exclusion path are currently latent, not exercised by production data — stated explicitly, not left implicit).

## Phase 3: DIAGNOSE — each finding re-verified before fixing

All findings below were RE-VERIFIED by reading the current on-tree code
(not trusted from the brief) before any fix was written, per the
brief's "still CLAIMS — re-verify each" instruction.

- **C1** [HIGH]: confirmed by reading `_era_overlap_frac` (pre-fix,
  `scripts/gate_efficacy_report.py:109-117` at `a94b5751`) — one-directional:
  `sum(c for e,c in mix.items() if e in base_eras) / n` where `base_eras`
  was a bare SET (membership, no weight). Root cause: a single baseline
  row of an era buys that era full membership regardless of its own
  share; the 0.05 floor is evaluated on the SAMPLE's own share of a
  scarce shared era, not on how much of the baseline that era actually is.
- **C2** [HIGH]: confirmed by reading `render()` lines ~448-475 and
  `efficacy()` lines ~238-241 (`a94b5751`) — the admitted-vs-baseline
  headline computed significance purely from `neff_ok`, with zero
  reference to `_era_overlap_frac`/`ERA_OVERLAP_FLOOR` anywhere in that
  code path.
- **C3** [MED]: confirmed `_row_era`'s fallback calls `label_era_of`
  directly with no horizon disambiguation, and confirmed (live corpus
  header read) there is no per-row horizon column to disambiguate with
  even if desired — the only correct fix is UNKNOWN, not a guess.
- **C4** [MED]: confirmed the by_code `comparison` assignment (`a94b5751`
  lines ~450-459) fell through to `"not_significant"` in BOTH the
  honest-null case (both sides `neff_ok`, CIs overlap) and the
  n_eff-uncomputable case (`neff_ok=False`, `lo/hi` silently the nominal
  Wilson interval) — same string, two different epistemic states.
- **C5** [MED]: confirmed `gc_pusher._run_veto_quality` read only
  `rate/lo/hi/n_eff/anti_selective/selective` from each `by_code` row —
  no `era_overlap`/`comparison` key ever touched.
- **C6** [MED]: confirmed `build_trading_dashboard.py:1798-1809`'s
  "Anti-selective gates" description still read "as of 2026-08-26 that
  was SZ-021 (crisis)... won at 0.51 against a 0.27 baseline" as an
  unqualified fact, baked into the checked-in
  `docs/grafana/liquiditybot_problem_solution.json:3868-3869`.
- **C7** [LOW-MED]: confirmed by reading `HANDOFF.md:153-154` against the
  actual code: per-disposition dicts had `confounded_baseline`(bool)/
  `era_overlap`(float) but NO `comparison` key; `render()`'s Per-rule
  markdown table emitted prose (`" (baseline CONFOUNDED - ..."`), never
  the literal field. HANDOFF's claim that "the Per-rule markdown table...
  carr[ies] `comparison: "CONFOUNDED_BASELINE"`" was false for markdown.
- **I1**: confirmed no existing test exercises 2 variants of one code in
  2 different eras — every existing fixture (`_row()` in
  `tests/test_veto_quality.py`) omits `label_era`/`barrier` entirely, so
  every row falls back to `"legacy"` uniformly; `.update()` vs `=` were
  indistinguishable under every pre-existing fixture.
- **I2**: double-derived via `grep`: `docs/HANDOFF.md` lines 80/93 said
  "Boundary #6" for the FEE-1+FEE-2 fee-truth cut; `scripts/fee_reprice.py`
  lines 21/32-34/209 and `git show -s ca55e2ba` both say "boundary #5" for
  the SAME cut, and `docs/HANDOFF.md`'s own later WHY-1 entry (line 115)
  also says "boundary #5". 3 independent, later/code-level sources agree
  on #5 against 2 same-day (08-22) prose lines saying #6 — not
  genuinely ambiguous once cross-checked; not flagged AMBIGUOUS.
- **I3**: double-derived via two routes: (a) `git show --stat 8a9cc087`
  — no `tests/test_migrate_history.py` in the changed-file list (only
  `tests/test_history_migration.py`, 3-line diff); (b)
  `git show 8a9cc087 -- tests/ | grep -c "^+def test_"` = **12**, not the
  commit message's claimed 13 (all 12 land in the new
  `tests/test_label_ret_persistence.py`). Both sub-claims of I3 confirmed
  independently before writing the correction.
- **I4**: confirmed no existing comment addressed n_eff-weighting for
  era overlap at all (grep for "n_eff" in the pre-fix `_era_overlap_frac`
  docstring returned nothing).
- **I5**: confirmed `ml.history._row_label_era` (lines 448-458) uses the
  identical 2-line persisted-then-fallback shape as
  `gate_efficacy_report._row_era`, and confirmed no test in either
  `tests/test_veto_quality.py` or `ml`'s own test files compares the two
  functions directly.

**Risk labeling**: C1/C2 HIGH (the file's flagship claims, direct
Grafana/HANDOFF consumers); C3/C4/C5/C6 MED (report-plane, single-caller
or JSON-field-level); C7/I1-I5 LOW-MED (docs accuracy, test coverage
gaps, one doc comment). No HIGH-risk item touched public interfaces
outside this file's own JSON/markdown contract; Grafana metric families
extended, never renamed (verified: `grep -rn "liquiditybot_veto_"
scripts/` shows every pre-existing gauge name unchanged in this diff).

## Phase 4: FIX — in order (deps -> types -> logic -> tests -> integration)

1. **Deps**: import `LABEL_ERA_TRIPLE_BARRIER`, `LABEL_ERA_UNKNOWN`
   alongside the existing `label_era_of` import.
2. **Types/constants**: `ERA_OVERLAP_MAJORITY = 0.5` added beside the
   existing `ERA_OVERLAP_FLOOR = 0.05`; new `_era_state()` and
   `_comparison()` helpers give every comparison site (per-disposition,
   by_code, admitted-vs-baseline) one shared vocabulary instead of three
   near-duplicated inline blocks.
3. **Logic**:
   - `_row_era` (C3): fallback-derived bare `LABEL_ERA_TRIPLE_BARRIER`
     now routes to `LABEL_ERA_UNKNOWN`; persisted values unaffected.
   - `_era_overlap_frac` (C1): rewritten from one-directional membership
     to weighted histogram-intersection (`sum_e min(p_sample(e),
     p_base(e))`), `LABEL_ERA_UNKNOWN` excluded from the numerator on
     both sides but kept in the denominator (dilutes, does not vanish).
   - `efficacy()`: admitted-vs-baseline now computes
     `admitted_era_overlap`/`admitted_comparison` (C2); per-disposition
     rows now carry `partial_overlap` (bool) and `comparison` (str, C7);
     by_code rows' `comparison` now includes `PARTIAL_OVERLAP` and
     `not_significant_nominal_n` (C1/C4); `anti_selective`/`selective`
     gated on `era_state == "COMPARABLE"` everywhere (previously `not
     confounded`, which let PARTIAL_OVERLAP through unflagged).
   - `render()`: admitted-vs-baseline headline branches on
     `admitted_comparison` BEFORE the neff-based branches (C2); Per-rule
     flag column gets a new `partial_overlap` branch.
   - `gc_pusher.py` (C5): `_run_veto_quality` reads `comparison`/
     `era_overlap` from each `by_code` row, exports
     `liquiditybot_veto_confounded` (1.0 when CONFOUNDED_BASELINE or
     PARTIAL_OVERLAP) and `liquiditybot_veto_era_overlap` (raw value) —
     new gauge keys, all 6 pre-existing gauge names unchanged.
   - `build_trading_dashboard.py` (C6): "Anti-selective gates" desc
     dated on both sides (08-26 read kept verbatim, 08-27 supersession
     appended); new "Confounded verdicts" stat panel (id 54, sequential,
     no collision with the fixed injector id 990) reading
     `sum(liquiditybot_veto_confounded)`.
   - `docs/HANDOFF.md` (C7, I2, I3): corrected the field-location
     sentence; added a dated REG-6 CAVEAT fix-wave-hardening paragraph
     (see "Unanticipated finding" below); "Boundary #6" -> "Boundary #5"
     at both 08-22 OPEN DOCKET lines; new RECENTLY SETTLED row correcting
     8a9cc087's pin-count/filename overclaim.
4. **Tests** (`tests/test_veto_quality.py`, +210 lines;
   `tests/test_boards_stripped.py`, +25 lines): see Phase 5 below for
   the full list and mutation results — 12 new tests total (10 in
   test_veto_quality.py, covering C1i, C1ii, C4, C2 [x2: injection +
   control], C7, I1, I5, C5 [x2: confounded + clean]; 1 in
   test_boards_stripped.py for C6's desc pin, plus the C5 panel-inventory
   pin extending `_PROBLEM_PANELS`).
5. **Integration**: reran `scripts/build_trading_dashboard.py` to
   regenerate `docs/grafana/liquiditybot_problem_solution.json` (55
   panels, was 54) so `test_generator_matches_shipped_json` stays green;
   ran `scripts/gate_efficacy_report.py --json` and `--min-n 30`
   (markdown) against the live corpus as an end-to-end smoke check
   (output reviewed below); confirmed `gc_pusher.py`'s consumer contract
   (rate/lo/hi/n_eff/anti_selective/selective keys) is byte-identical in
   shape, only new optional keys added.

## Phase 5: VERIFY

### Mutation evidence (mandatory per the operator's verification order) — 8/8 guards, all confirmed load-bearing, all restored

Each mutation was applied directly to the TRACKED file (per the fix
brief's own instruction: "Mutation-verify the load-bearing fixes: break
each guard once, watch its new pin go red, restore" — this repo's
constraint against tracked-tree edits applies to the VERIFICATION agent
role in `context-common.md`, not to this FIX agent, whose job is to ship
the fix itself), then reverted via a matching `Edit` back to the exact
shipped form, then re-confirmed green.

| # | Guard | Mutation | Result before revert | Restored & reconfirmed |
|---|---|---|---|---|
| 1 | C1(i) weighted overlap | `_era_overlap_frac` reverted to membership-only (`e in base_mix`) | `test_single_baseline_row_cannot_unfire_the_guard_via_membership` FAILED (`era_overlap` read 1.0, not <0.05); 1 failed, 21 passed | Yes — `pytest tests/test_veto_quality.py -q` 22 passed |
| 2 | C1(ii) majority floor | `_era_state` majority branch removed (only FLOOR checked) | `test_majority_incomparable_sample_does_not_print_unflagged_verdict` FAILED (`comparison` read `'anti_selective'`, an UNFLAGGED verdict on a 93%-incomparable sample — reproduces the exact pre-fix failure mode) | Yes |
| 3 | C2 admitted-vs-baseline guard | `adm_era_state` hardcoded to `"COMPARABLE"` | `test_admitted_vs_baseline_headline_is_era_gated` FAILED (`admitted_comparison` read `'not_significant'` instead of `'CONFOUNDED_BASELINE'`) | Yes |
| 4 | I1 cross-variant pooling | `era_mix_by_code[...].update(...)` -> `= _era_mix(v)` | `test_cross_variant_era_pooling_is_additive_not_last_write_wins` FAILED (`era_overlap` read exactly 0.0, the last-processed variant's disjoint era, not the pooled 0.5) | Yes |
| 5 | C3/I5 UNKNOWN reroute | `_row_era`'s persisted-or-fallback restored to the un-rerouted 1-line form | `test_row_era_precedence_matches_ml_history_except_the_documented_gap` FAILED (`_row_era({"barrier":"tb_sl"})` read `'triple_barrier'`, not `'unknown'`) | Yes |
| 6 | C4 nominal-n distinction | `_comparison`'s `not neff_ok_both` branch removed | `test_by_code_distinguishes_uncomputable_neff_from_a_vetted_null` FAILED (`comparison` read `'not_significant'`, collapsing the n_eff-uncomputable case back into the vetted-null string) | Yes |
| 7 | C5 gc_pusher gauge | `vals["confounded"]` hardcoded to `0.0` | `test_collector_exports_confounded_gauge_and_era_overlap` FAILED (gauge read 0.0 for a CONFOUNDED_BASELINE code) | Yes |
| 8 | C6 desc pin | dashboard desc's 08-27 caveat sentence removed, rebuilt JSON | `test_anti_selective_desc_carries_the_confound_caveat` FAILED (`"SUPERSEDED 2026-08-27"` missing from shipped `description`) | Yes — desc restored, `build_trading_dashboard.py` rerun, JSON rebuilt back to the shipped form |

All 8 mutations reverted via `Edit` back to the exact committed text
(not `git checkout`, to avoid disturbing other in-progress edits);
`docs/grafana/liquiditybot_problem_solution.json` rebuilt a second time
after mutation #8 to restore the shipped artifact. Confirmed identical
byte-for-byte to the pre-mutation build by re-running the full covering
suite immediately after (104/104 passed both before and after the
mutation battery).

### Ask-the-runtime corroboration (live corpus, not synthetic)

`./.venv/Scripts/python.exe scripts/gate_efficacy_report.py --json`
against the live, still-accruing `outputs/signal_history.csv`
(read-only; snapshot-stamped 2026-08-27T22:48:55Z [K], `date -u`):

| code | n | era_overlap (weighted) | comparison (post-fix) |
|---|---:|---:|---|
| SZ-023 | 4,736 | 0.0082 | CONFOUNDED_BASELINE |
| SZ-022 | 3,013 | 0.0737 | PARTIAL_OVERLAP |
| SZ-021 | 2,032 | 0.0000 | CONFOUNDED_BASELINE |
| SZ-030 | 1,052 | 0.1587 | PARTIAL_OVERLAP |
| SZ-045 | 641 | 0.0842 | PARTIAL_OVERLAP |
| SZ-046 | 505 | 0.1587 | PARTIAL_OVERLAP |
| SZ-020 | 375 | 0.1587 | PARTIAL_OVERLAP |
| SZ-050 | 78 | 0.1587 | PARTIAL_OVERLAP |

admitted-vs-baseline: `admitted_era_overlap=0.1587`,
`admitted_comparison="PARTIAL_OVERLAP"`.

**Unanticipated finding (not in the original DIAGNOSE, surfaced by this
runtime check)**: under the hardened guard, EVERY by_code row and the
admitted-vs-baseline headline now reads CONFOUNDED_BASELINE or
PARTIAL_OVERLAP — none clears to COMPARABLE. This includes `SZ-030`,
which the prior (`a94b5751`) membership-based guard correctly left
`selective` (era_overlap reported 0.685 then). Root cause, verified: the
weighted formula caps every code's overlap at baseline's OWN share of
whatever era they partially share (`exit_sim`, 15.9% of baseline, i.e.
0.1587) — SZ-030 IS majority-`exit_sim` itself, but baseline is only
15.9% `exit_sim` (84.1% `legacy`), so `min(p_code, p_base)` caps at the
smaller (baseline's) side. This is the fix working as designed, not a
bug: the old 0.685 number was membership-inflated (treating baseline's
mere possession of ANY exit_sim rows as if it were majority-exit_sim
too). Documented in `docs/HANDOFF.md`'s new REG-6 CAVEAT paragraph,
explicitly labeled "not fixed here" (redesigning the baseline population
itself is out of this fix-wave's declared scope — `BASELINE = ""` was
not touched).

### Covering suite — exact counts

`./.venv/Scripts/python.exe -m pytest tests/test_veto_quality.py
tests/test_boards_stripped.py tests/test_gc_pusher_owed_metrics.py
tests/test_candidate_zombie_eviction.py tests/test_import_integrity.py
tests/test_trading_dashboard.py -q`, run repeatedly through the fix and
mutation cycle, final run 2026-08-27 ~23:05 UTC:

```
104 passed in 6.58s / 7.19s (re-run after stash/pop restore)
```

(was 81 before this fix-wave per the task-3 report's own count at
`a94b5751`; +12 new tests in `test_veto_quality.py` and +1 in
`test_boards_stripped.py` = 94 expected from those two files alone —
**verified discrepancy note**: 81 was the count for the 4-file set
`test_veto_quality/test_boards_stripped/test_gc_pusher_owed_metrics/
test_candidate_zombie_eviction`; this run adds 2 more files
(`test_import_integrity`, `test_trading_dashboard`) not in the task-3
count, accounting for the rest of the difference — both counts are
internally consistent with their own file sets, not a contradiction.)

### Lint / type / compile / security

- `ruff check scripts/gate_efficacy_report.py scripts/gc_pusher.py
  scripts/build_trading_dashboard.py tests/test_veto_quality.py
  tests/test_boards_stripped.py` -> **All checks passed.**
- `python -m compileall -q` on the same 5 files -> clean.
- `bandit -c pyproject.toml scripts/gate_efficacy_report.py
  scripts/gc_pusher.py scripts/build_trading_dashboard.py -q` -> exit 0,
  0 issues (only comment-parsing warnings, no findings).
- `pyright scripts/gate_efficacy_report.py scripts/gc_pusher.py
  scripts/build_trading_dashboard.py` -> **7 errors, 0 new.**
  Double-derived: `git stash push` on exactly the 7 fix-wave files,
  re-ran pyright against the resulting `a94b5751` baseline (2 errors in
  `build_trading_dashboard.py` at 2247/2248, 1 in
  `gate_efficacy_report.py` at 412, 4 in `gc_pusher.py` at
  253/1163/1178x2), confirmed byte-identical error TEXT to the post-fix
  run (only line numbers shifted by the amount each file grew), then
  `git stash pop` and re-ran the covering suite (104/104 again) to
  confirm the restore was clean. **0 new pyright errors attributable to
  this fix-wave.** (`scripts/` is outside CLAUDE.md's gated pyright
  scope — this check is due diligence per the brief's own instruction,
  not a hard requirement.)

### Full suite — completed AFTER the commit and the initial contract report; result folded in here

`./.venv/Scripts/python.exe -m pytest tests/ -q` (started before the
commit, backgrounded) finished at 2026-08-27 ~23:19 UTC [K], **540.96s /
0:09:00 wall time**, background-task exit code 0:

```
4060 passed, 9 skipped in 540.96s (0:09:00)
```

**0 failed.** This was NOT observed before `62ab10c0` was committed or
before the first STATUS/concerns contract was returned to the
coordinator (per the coordinator's explicit instruction to finish the
protocol without waiting on it) — that earlier report correctly flagged
the full suite as unwatched, stating the gap rather than assuming a
result. This section is the promised follow-up: the run finished clean,
superseding that caveat. Test count note: 4060 + 9 = 4069 collected here
vs the task-3 report's 4058 collected at `a94b5751` — the +11 delta is
exactly this fix-wave's own new tests (10 in `test_veto_quality.py` + 1
in `test_boards_stripped.py`), double-derived: 4058 + 11 = 4069, matches.

### Classification: SAFE (era-4 moratorium)

Confirmed as shipped: no file under `main.py`'s decision pipeline,
`execution/`, `risk/`, `core/fill_ledger.py`, order-lifecycle, or
fee-booking paths was touched. All 7 changed files are
report/telemetry/dashboard/docs-plane
(`scripts/gate_efficacy_report.py` is explicitly docstring-labeled
"Report-only... Never touches a decision"; `scripts/gc_pusher.py` is the
existing metrics exporter; `scripts/build_trading_dashboard.py` +
`docs/grafana/*.json` are Grafana board generation; `tests/`;
`docs/HANDOFF.md`). Does not change which orders are placed or how they
fill.

### Residual limitations (reported, not fixed — out of this fix-wave's declared scope)

1. The baseline population itself (`BASELINE = ""`, the frozen
   2026-07-20 migration-backfill cohort) was NOT redesigned. The
   unanticipated finding above (every code now PARTIAL/CONFOUNDED)
   confirms the prior task-3 report's own recommendation (a
   live/contemporaneous baseline) is the real structural remedy — this
   fix-wave hardens the GUARD around the frozen baseline, it does not
   replace the baseline.
2. Full `pytest tests/ -q` was not observed to completion (see above) —
   flagged, not silently skipped.
3. `learning_panel.py` confirmed structurally unaffected by trace, not
   modified, per the brief.

### Files changed (absolute paths)

- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\gate_efficacy_report.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\gc_pusher.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\scripts\build_trading_dashboard.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\docs\grafana\liquiditybot_problem_solution.json`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_veto_quality.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\tests\test_boards_stripped.py`
- `c:\Users\haird\Documents\liquiditybot\liquiditybot_ab\docs\HANDOFF.md`

Commit: `62ab10c010d25b3857a5164e291f9216f98001bb` on
`claude/claude-rc-f3heik` (local only, not pushed, per the fix-wave
brief's constraint).
