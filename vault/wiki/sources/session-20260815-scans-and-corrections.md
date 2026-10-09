---
title: Session 2026-08-15 — Two Scans, Six Non-Resolving Instruments, and Four Corrections the Author Made to Himself
category: source
summary: "The day the instruments were audited instead of the strategy. Two adversarially-verified scans (232 candidates to 15 confirmed, then 507 to 10) plus direct measurement established that SIX instruments cannot currently resolve their own questions: the era-4 gate (effective n 4.3 of 14), the overfit battery (SYNTHETIC below its 640 row floor), OF-4 plateau (zero-entry recording), OF-5 DSR (22 conviction vs 30), gate_efficacy_report (whole-corpus SE inflation x8.07 on mean uniqueness 0.0154), and cost_truth_report (hedge legs booked taker, priced as maker). None is broken; each degrades honestly and says so somewhere, and nothing aggregated the caveats — so a stack of passing lines read as evidence. Also records four corrections the session author made to his own claims, two agent headline numbers that failed re-derivation, and the measured finding that adversarial refuters killed under 1% while finder ship-criteria killed 99%"
tags: [instruments, scans, corrections, effective-n, false-green, workflow-design, epistemics]
sources: 1
source_path: repo docs/quant/2026-08-15_agent_workflow_doctrine.md + commits 61c3b5c1..f756676e
source_date: 2026-08
authors: [session-4b5e9197]
ingested: 2026-08-15
updated: 2026-08-15
---

# Session 2026-08-15 — Scans and Corrections

**Paper/real boundary (domain rule 9):** every number below is **sim-side** or
**repo-side**. The bot is DRY_RUN at equity ~$799. No venue truth is claimed.

**Status:** measured, battery-green at each commit (`pytest` 3687 passed / 1
skipped at the final one, smoke 219/0, assurance 48/0, overfit 7/0, ruff clean,
pyright shipped scope **0**, bandit 0, compileall 0). Commits `61c3b5c1`,
`ba9034e5`, `523fde68`, `c8def633`, `c5ce9d0b`, `c7a79fbe`, `f756676e` — all
pushed to `claude/remote-control-e3h815`, `main` and the feature branch.

---

## 1. Six instruments, none resolving

This is the session's headline and it is a statement about **instruments**, not
about the strategy.

| instrument | can it answer its question today? | measured |
|---|---|---|
| era-4 verdict gate | **no** | effective n **4.3 of 14** (mean uniqueness 0.306, SE optimistic ×1.81) — **⚠️ as-of 2026-08-15; SUPERSEDED**, see note below |
| overfit battery OF-1…7 | **no** | SYNTHETIC benchmark; loaded rows 346–352 (moving) against a 640 floor; **0** from a worktree |
| OF-4 plateau | **no** | all three probes report `entries [0,0,0]` — a plateau test over a recording that opens no positions |
| OF-5 deflated Sharpe | **not yet** | 22 conviction-marked live trades against a floor of 30; conviction accrues ~0.2/day |
| `gate_efficacy_report` | **no** | whole-corpus effective n **162.2 of 10,567**, mean uniqueness **0.0154**, **SE inflation ×8.07** |
| `cost_truth_report` | **no** | hedge opens submitted `post_only=False` and booked taker, then printed as "mean entry-leg vs configured maker" — 36.23 bps printed against 28.005 true |

> ⚠️ **Row 1 SUPERSEDED 2026-08-16 (the row is an as-of reading, not a state).**
> Re-derived by **running** `scripts/cohort_eval.py` at **2026-08-16T21:01:13Z**:
> **n = 16 of 50**, effective n **5.249648119206663**, mean uniqueness
> **0.32810300745041643**, SE inflation **×1.7458016289694764**, per-trade sd
> **2.559127919795581%** (double-derived as `gross_se_pct × √16`), observed gross
> mean **+0.6576563162731225%**. **The verdict does not change — it hardens:** at
> n=50 the resolvable floor is **1.2636647844398836%** at 2·SE (**1.92x** the
> observation) and **1.7701322903683439%** at 80% power (**2.69x**), and the two
> conventions **differ by 40.08%** with **neither named** in the 527-line UNSIGNED
> decision table. *(Row 2's row count also moves — 347 at the last recorded run;
> the relation `loaded < 640 ⇒ SYNTHETIC` is what is stable.)*
> — [[sources/session-20260816-catchup-08-12-to-08-16]] §1-2, [[synthesis/owed-measurements]] item 82

**Not one is broken.** Each degrades honestly and says so somewhere in its own
output. What did not exist was anything that aggregated the caveats, so a stack
of passing lines was read as evidence. That is
[[concepts/false-green]] at the level of the *reader* rather than the gate.

## 2. The ×8.07 retires numbers this corpus has been quoting

Measured directly on `outputs/signal_history.csv`, whole corpus, using the same
average-uniqueness algorithm `scripts/gate_truth_report.py` has applied since
2026-07-29:

```
n = 10,567 spans   effective n = 162.2   mean uniqueness = 0.0154   SE ×8.07
```

Every Wilson interval in `gate_efficacy_report`'s ~29-row per-rule table is
computed at **nominal n** and is therefore roughly **eight times too narrow**.

**Consequence, stated plainly: that report is not measuring gate selectivity.**
Not measuring it *wrongly* — the resolution is not present. The `ANTI-SELECTIVE`
flags, the per-rule CIs and the headline separation are artifacts of counting
rows as though they were facts.

This retires two figures in circulation, including one this session opened with:

- **"the gate selects against itself, −2.3%"** — additionally era-confounded.
  `gate_efficacy_report.py:105` bins on disposition only and never reads
  `label_era` (0 occurrences in the file). The baseline arm is **84.1% legacy
  with zero `triple_barrier`**; the admitted arm has **zero legacy**.
- **"`SZ-023: p 0.28 below bar 0.55` is ANTI-SELECTIVE +17.5%"** — does not
  survive effective n; at n_eff the Wilson intervals overlap and the flag does
  not fire.

**Era-matched separations, re-derived** (entered vs not, per `label_era`):

| era | entered | rest | separation |
|---|---|---|---:|
| `exit_sim` | 31/247 = 0.1255 | 351/2485 = 0.1412 | **−1.57pp** |
| `triple_barrier` | 3/46 = 0.0652 | 1333/5282 = 0.2524 | **−18.71pp** |
| `triple_barrier_h432` | 1/6 = 0.1667 | 85/346 = 0.2457 | −7.90pp (n=6) |

**The eras disagree by an order of magnitude.** There is no single separation
number, and the defect is not a wrong value — it is that a pooled statistic is
computed at all, in the one report that grades the gate
([[concepts/pooled-populations]]).

## 3. Two scans, and what the kill rates mean

| scan | candidates | killed by finders | killed by refuters | confirmed |
|---|---:|---:|---:|---:|
| preventive maintenance (6 subsystems) | 232 | 215 | **2** | **15** |
| defect-class recurrence (5 classes) | 507 | 494 | **3** | **10** |

**Adversarial verification killed under 1% in both.** The strictness that did
the work lived in the *finder's* ship-criteria — a finding that contradicts
standard multi-agent practice and is recorded with its caveat in
`docs/quant/2026-08-15_agent_workflow_doctrine.md`: refuters still corrected
severity and fix-class on survivors, and finders may have been strict *because*
a refuter was known to follow. Both effects are unseparable from this data.

**One class came back CLEAN** — "a reader that writes" produced zero further
instances, so `core/session_digest.py:139` was a genuine one-off rather than a
habit. A clean class is a result and must not be re-hunted blind.

## 4. Four corrections the author made to his own claims

Recorded per domain rule 3, because the retraction is the content.

1. **"`champion_bar` ratchets the wrong way; the challenger squeaked under by
   0.00049."** WRONG. `champion_bar` is `monitor.champion_brier` recorded for
   observability only (`main.py:6467`), never a threshold. The real mechanism is
   ML-083's era-orphan unlock applying the bare cold-start bar
   ([[concepts/deploy-deadlock]] §third polarity).
2. **"moomoo is unavailable because of US market hours."** REFUTED by its own
   test: availability 34.5% during 13–19Z RTH vs **39.1% off-hours**, and 00Z
   runs 27/30. No session pattern.
3. **"moomoo ships the neutral constant."** UNDERSTATED. `opt_iv_skew` is pegged
   at **−3.0**, the clip bound — **−5.93 sigma** given mu −0.1347 / sd 0.4831,
   and with weight −0.3998 a **+2.37 logit** shift on every prediction.
   `ml/contracts.py:62` bounds the feature at (−3, 3), the same range as the
   feed's clip, so the pegged value is **legal by construction** and no guard
   fires.
4. **"ALGO-5's ~30-uncensored-path trigger has fired, 6× over, at 182."**
   RETRACTED. Item 67's measure is the ALGO-4 ledger
   (`outputs/trade_paths.csv`, **10 rows**); the 182 were `signal_history`
   barrier resolutions — a different population whose name also reduces to
   "paths".

**Two agent headline numbers also failed re-derivation**: a war-room claim that
fee-free gross is negative on both statistics over 414 positions (entry-only is
*positive* on both; medians reproduce, means do not), and a scan claim of
−15.83pp era-matched on `exit_sim` (measured −1.57pp). Every **pointer** those
agents gave was correct. The rule extracted: **ship an agent's pointer, never
its number.**

## 5. The IDE's 1546 problems are two scopes, both correct

Reproduced exactly: `pyright` over the workspace returns **1546** diagnostics
(1545 error, 1 warning) across **489 files** analyzed.

| area | diagnostics |
|---|---:|
| `tests/` | **1533** (99.2%) |
| `scripts/` | 13 |
| **shipped scope** | **0** |

`reportArgumentType` (912) and `reportAttributeAccessIssue` (483) are 90% of the
total — the signature of test doubles: a `SimpleNamespace` passed where a real
object is annotated. The DoD gate passes an **explicit file list** (~96 files)
and holds zero; Pylance uses `diagnosticMode: "workspace"` and
`pyrightconfig.json` carries **no `include` key**, so it scans 489. CLAUDE.md
already says tests/scripts are outside the gate.

**Not a defect, but not nothing**: this session's `test_auto_retrain_stale_gate_cas`
failure was exactly a test double missing an attribute — the class pyright
flags 1,533 times and which is therefore invisible.

**RESOLVED 2026-08-15 by an `include` in `pyrightconfig.json`** naming the
shipped scope, so the IDE and the gate now agree: `filesAnalyzed` 489 → **96**,
diagnostics **1546 → 0**, and the explicit DoD invocation still reports 0.

**The 13 `scripts/` diagnostics are recorded HERE because the include hides
them and they are NOT test doubles** — they are genuine None-flow warnings in
report tools, and a silently hidden warning is the drift this corpus tracks:

| file:line | rule | message |
|---|---|---|
| `cost_truth_report.py:346, :373, :401` | `reportOptionalOperand` | `Operator "*" not supported for "None"` |
| `debug_cycle.py:119` | `reportOptionalMemberAccess` | `"splitlines" is not a known attribute of "None"` |
| `defensive_cadence_report.py:101` | `reportAttributeAccessIssue` | `Cannot access attribute "reconfigure" for class "TextIO"` |
| `fill_hazard_report.py:176` | `reportGeneralTypeIssues` | `"None" is not iterable` |
| `gate_efficacy_report.py:168` | `reportArgumentType` | `dict[str, float \| int]` assigned to an `int` parameter |
| `gc_pusher.py:203` | `reportGeneralTypeIssues` | **`Code is too complex to analyze`** — pyright gave up on this function |
| `label_transfer_filter.py:185` | `reportOptionalSubscript` | `Object of type "None" is not subscriptable` |
| `overfit_check.py:244, :245` | `reportArgumentType` | `dict \| None` passed where `dict` is required |
| `quant_trials.py:416` | `reportOperatorIssue` | `"<=" not supported for "float" and "float \| None"` |
| `train_meta.py:248` | `reportAssignmentType` | tuple-shape mismatch |

Severity is LOW for a paper bot — these are report tools, several already
wrapped in `try/except`, and none sits in an order path. But `gc_pusher.py:203`
is worth its own note: **"code is too complex to analyze" means that function
has no type coverage at all**, which is a different statement from "it type-checks".

## 6. Shipped

Measurement and lineage only; **no execution-era boundary is minted**.

- **DL-2** — all 6 git call sites in the 4 headless sidecars make git fail
  rather than ask; `telemetry_backup`'s two calls were **unbounded** and are now
  bounded.
- **Cohort instruments** — fill-era, model-era and selection-era contamination
  sections, geometry breakeven, effective n, and both fee-free populations, all
  on `scripts/cohort_eval.py` with the pre-registered selection **byte-identical**.
- **Model lineage** — `orphan_ratio` on every retrain row; `deployed` **and**
  `retired` events at both cutover sites (the registry held 134 `registered`
  and **zero** of either).
- **Six preventive-maintenance fixes**, of which the sharpest was
  `core/session_digest.py:139` constructing an `AuditTrail` — a **writer** —
  against the live hash-chained `audit.jsonl`, hourly.
- **The overfit corpus banner** on the summary line.

## Related

- [[concepts/overfit-battery]] §the battery is currently on the synthetic benchmark
- [[concepts/deploy-deadlock]] §third polarity · [[concepts/false-green]] §the eighth way
- [[concepts/no-orphan-claims]] — governance rule 18, filed this session
- [[synthesis/owed-measurements]] items 73 and 74
- [[sources/session-20260814-cohort-instruments]] — the preceding day's ingest
- [[concepts/pooled-populations]] · [[concepts/era-exclusion]] · [[concepts/probe-livelock]]
