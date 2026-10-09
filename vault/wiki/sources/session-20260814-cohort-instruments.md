---
title: Session 2026-08-14 — Cohort Instruments, the ML-083 Unlock Without a Floor, and a Battery That Could Not Run
category: source
summary: Four confirmed findings from a measurement-only session — fills.csv carries rows whose exec_era field is ABSENT (not blank), so the standing decide-by-ts rule returns the wrong era for exactly them; ML-083's era-orphan unlock fired at a 48x ratio and promoted a negative-skill model into the accruing verdict window; the h432 geometry needs a 42.9% target-hit rate and gets 22.4% (context for owed-67, NOT its trigger — the session's own conflation of barrier resolutions with trade paths is filed as a retraction); and the DoD battery had been dying at collection with "no tests ran"
tags: [exec-era, cohort, ml-083, deploy-gate, algo-5, false-green, geometry, moratorium]
sources: 1
source_path: repo docs/quant/2026-08-14_model_promotion_migration_design.md + commits 61c3b5c1, 258d2eeb
source_date: 2026-08
authors: [session-4b5e9197]
ingested: 2026-08-14
updated: 2026-08-14
---

# Session 2026-08-14 — Cohort Instruments

**Paper/real boundary (domain rule 9):** every number below is **sim-side** or
**repo-side**. No venue truth is claimed. All P&L, fill, barrier and expectancy
figures come from the simulated execution path.

**Status:** measured, battery-green (`pytest` 3656 passed / 1 skipped, smoke
219/0, assurance 48/0, overfit 7/0, ruff clean, pyright shipped scope 0 errors,
bandit 0, compileall 0), committed at `61c3b5c1` (instruments) and `258d2eeb`
(designs). Filed same-session per governance rule 12.

---

## Finding 1 — `exec_era` ABSENT is not `exec_era` blank

**This qualifies the standing rule in [[synthesis/comparability-boundaries]].**

That table currently records: *"pre-schema rows are deliberately blank = decide
by ts."* Measured 2026-08-14 on `outputs/fills.csv`:

- header **17** columns; `exec_era` is index **16 — the last**
- row field-width histogram: **`{17: 1059, 16: 6}`** (double-derived; a first
  pass using naive comma-splitting wrongly reported 170 and was discarded)

Six rows carry **16 fields**. The field is **absent**, not empty. `csv.DictReader`
maps a missing trailing field to `None`, which is distinguishable from `""`.

The distinction is decision-grade because the decide-by-ts rule gives the
**wrong** answer for exactly these rows: their `ts` reads era-7 while their fill
physics is pre-boundary-#4. `git reflog` places the live tree at `21769fb8`
(2026-08-07) from 08-11 19:50 until the 08-12 20:21 fast-forward — and
boundaries #3, #4 and cut #7 are all **non-ancestors** of that commit. Those
fills were granted by a simulator with both the TTL-hazard compounding bug and
the ~1.88x near-touch double-count live.

Corrected three-way rule, now implemented in `scripts/cohort_eval.py`:

| `exec_era` | meaning |
|---|---|
| `None` (field absent) | **stale binary** — writer's `COLS` predates the stamp |
| `""` (blank) | pre-stamp row of a stamp-aware writer — decide by ts |
| stamped | authoritative |

**Cohort impact: 4 of 13 accruing era-4 trips contain a stale-binary leg.** A
fifth was open at measurement and joins on close. Reproduced independently by
`cohort_eval`'s new section, by a different code path than the original
forensics.

## Finding 2 — ML-083's era-orphan unlock has no floor

Extends [[concepts/deploy-deadlock]] with a third polarity.

`main.py:6387` — when the champion's `trained_rows` watermark exceeds the
current matrix, the unlock sets the champion badge aside and applies the
cold-start bar (`Brier < 0.25`) via `should_deploy(..., ignore_champion=True)`.

Its own comment records the case it was built for on 2026-07-29: **4,823 vs
1,516 — a 3.2x orphan ratio**. The doctrine ("an unfalsifiable badge may not
gate forever") is sound and this page does not dispute it.

It fired on **2026-08-14T15:14:13Z at 10,217 vs 211 — a 48x ratio**:

| ts (UTC) | rows | live | champion_bar | oof_brier | deployed | selected |
|---|---:|---:|---:|---:|---|---|
| 08-13 20:25:49 | 10,296 | 314 | 0.21936 | 0.15997 | — | gbt |
| 08-14 09:13:47 | 181 | 5 | 0.21936 | 0.32251 | — | logistic |
| 08-14 15:14:13 | **211** | **5** | 0.21936 | 0.21887 | **YES** | logistic |
| 08-14 20:14:21 | 237 | 5 | 0.21887 | 0.17959 | — | logistic |

The deployed model's own `family_brier` was **0.33105** — worse than the 0.25 a
constant p=0.5 predictor scores. The only upstream floor is `len(X) < 60`
(`main.py:6237`), which 211 clears comfortably.

**The gate then defended the regression.** After deploy, `trained_rows` became
211, so `211 > 237` is false, the unlock stopped firing, and the next
challenger — with a *better* OOF Brier of **0.17959** — was rejected by the
like-for-like branch for having no shared row set. Correct fail-closed logic
protecting a worse incumbent.

> ⚠️ Retraction of this session's own first reading (domain rule 3): the initial
> account attributed the promotion to `champion_bar` "loosening" 0.15985 →
> 0.21936 and the challenger clearing it by 0.00049. That is **wrong**.
> `champion_bar` is `monitor.champion_brier` recorded for observability only
> (`main.py:6467`) and is not a threshold anything is compared against. The
> 0.00049 margin was coincidence. Mechanism is the ML-083 branch above.

## Finding 3 — the h432 geometry cannot pay, and owed-67's trigger has fired

A triple barrier pays gross only if the target is hit at least `sl/(pt+sl)` of
the time. Measured on all `triple_barrier_h432` rows (n=259 at 23:38Z, n=262
thirty minutes later — live file, values as-of):

- median `pt_frac` **2.064%**, median `sl_frac` **1.548%**, payoff **1.333**
- barriers: **`tb_pt` 41 · `tb_sl` 141 · `tb_time` 77**
- required target-hit rate **0.429**; realized **0.225**
- gross expectancy **−0.734% per barrier-resolved path, before any cost**

Arithmetic, not a fit, and **model-independent** — no selector rescues a
geometry that cannot pay. Two honesty caveats: the 77 time-stopped paths
resolve at neither barrier and are excluded (printed, never silent); and 119 of
123 recent rows are `candidate`, so this measures the geometry's
**counterfactual** expectancy, not realized strategy P&L. It is **not** the
era-4 verdict.

> ⚠️ **This session's own error, corrected before filing (domain rule 3).**
> *What was claimed:* that [[synthesis/owed-measurements]] item 67's ALGO-5
> trigger (**~30 uncensored trade paths**) had fired 6x over, at 182.
> *What refuted it:* item 67's measure is the **ALGO-4 trade-path ledger**
> (`outputs/trade_paths.csv`), which holds **10 rows** (read 2026-08-15T00:1xZ).
> The 182 are `signal_history` h432 **barrier resolutions** (41 `tb_pt` + 141
> `tb_sl`), overwhelmingly **counterfactual candidates** — a different
> population entirely.
> *What stands:* **the trigger has NOT fired; it is at 10/30.** The geometry
> measurement above is unaffected — it simply is not the trigger, and is
> context for that adjudication rather than a condition of it.
>
> Filed deliberately rather than quietly fixed: two measures whose names both
> reduce to "paths" were conflated, which is precisely the class the
> delegated-measurement discipline exists to catch, committed here by the
> session that wrote the discipline down.

## Finding 4 — the DoD battery had been dying at collection

An eighth entry for [[concepts/false-green]], and the sharpest yet because
there was no green at all — there was *nothing*.

A globally-installed SuperClaude pytest plugin **applies** four marks at
collection (`unit`, `integration`, `hallucination`, `performance`) while
registering only its own, different set. Under this repo's deliberate
`--strict-markers` that raises `INTERNALERROR` mid-collection: **"no tests ran
in 4.28s."** Not a failure count — an absence. Any session on this box running
the definition-of-done matrix was verifying nothing.

Fixed by **declaring** the four marks in `pyproject.toml`, not by
`-p no:superclaude` (a fix that survives only by being remembered is a debt
wearing a friendly face) and not by loosening strict mode (the existing comment
records the gate hole that strictness holds shut). Verified both ways: 3656
passed / 1 skipped with the plugin disabled, and **the identical 3656 / 1 with
it enabled** — so declaring the marks changed nothing about what runs.

## Supporting measurement — labels/day

Exact 24h window `[1786664298, 1786750698]`, snapshot 2026-08-14T23:38:18Z:

- **123 labels**, of which **119 candidate / 4 live**; all resolved, backlog **0**
- 12-day mean **124.5/day**, of which **3.0 live/day (2.4%)**
- **3 of the 4 live rows are `probe=1`.** The gate itself produced exactly one
  entry in 24h (BTC, `label=0`, −$0.42). 24h net **−$0.15**, which
  double-derives `pipeline_audit.md` by an independent route.
- `label_era` base rates span **40x**: `exit_sim_time_stop` 0.0065 (n=459) →
  `legacy` 0.2611 (n=1,781); current `triple_barrier_h432` 0.2239 (n=259) is
  **2.5% of the 10,559-row corpus**

The last line explains the retrain matrix of 211: [[concepts/era-exclusion]] is
working *correctly*; there is simply very little honest data.

## What shipped (measurement and lineage only)

Nothing touches entry decisioning, sizing, stop/exit geometry, fill simulation,
fee booking or the order lifecycle — **no execution-era boundary is minted**.

- `cohort_eval.py`: fill-era + model-era contamination sections, a
  `COHORT HOMOGENEITY` verdict line, and the geometry-breakeven readout. The
  pre-registered selection is byte-identical, pinned by
  `test_selection_rule_unchanged`.
- `main.py`: the registry recorded **134 `registered` events and ZERO
  `deployed`** ones, so the ledger could not answer the question its own
  docstring promises. Both cutover sites now record it.
- DL-2: all 6 git call sites in the four headless sidecars now make git fail
  rather than ask; `telemetry_backup`'s two calls were **unbounded** and are
  now bounded.

## The causal chain (the reason these are one docket item, not four)

1. The h432 geometry cut shrank the honest corpus to 259 rows.
2. Era exclusion correctly refused to pool it with retired geometries.
3. That made the orphan ratio **48x**, which fired ML-083.
4. ML-083 promoted a negative-skill model **into the accruing verdict window**.
5. **6 of 13** accruing trips straddle a mid-flight deploy; two distinct
   champions opened trips in the cohort.

Adjudicating ALGO-5 without the ML-083 floor re-runs this chain at the next
geometry cut.

## Related

- [[synthesis/comparability-boundaries]] — the authoritative cut table, qualified by Finding 1
- [[concepts/deploy-deadlock]] — ML-083, extended by Finding 2
- [[concepts/false-green]] — extended by Finding 4
- [[synthesis/owed-measurements]] — item 67's trigger fired (Finding 3)
- [[concepts/era-exclusion]] · [[concepts/label-era]] · [[concepts/evidence-floors]]
- [[concepts/pooled-populations]] — the 40x label-era base-rate spread
- [[synthesis/the-money-path-thesis]] — Finding 3 is geometry-side evidence, counterfactual, not the gate
