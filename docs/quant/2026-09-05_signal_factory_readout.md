# The signal factory read out, and the champion has no measurable skill

**Date:** 2026-09-05
**Class:** SAFE (measurement plane only — no config, engine state, or order path touched)
**Artifacts:** `scripts/signal_factory.py`, `tests/test_signal_factory.py`,
`outputs/signal_trials.csv` (ledger, schema v1)
**Re-derive, do not quote:** every number below is volatile. Commands are given
per section.

---

## 1. Why a factory at all

The repo evaluated signals one hand-picked batch at a time. That is how you get
"5 of 64 features read DIRECTIONAL" and cannot say whether five is a finding or
what chance produces — and how a search spread over ten sessions accumulates a
multiple-comparisons debt nobody counts.

`scripts/signal_factory.py` is the entry-signal sibling of the existing
`scripts/geometry_search.py` (which already does pre-registered grid +
Bonferroni for EXIT geometry). It reuses `decompose`, `null_calibration` and
`load_production_corpus` from `scripts/label_decomposition_report.py` and
re-implements no AUC, bootstrap or day block.

## 2. The readout

Grid `v1-2026-09-05`: **1,454 candidates** — 64 `sign()`, 64 `abs()`, 1,326
pairwise products drawn from the 52 features with enough distinct values to be
worth pairing.

| | |
|---|---|
| measured chance exclusion rate | **0.10** (from `null_calibration`, NOT the nominal 0.05) |
| DIRECTIONAL flags expected from noise | **145.4** |
| raw DIRECTIONAL flags observed | **217** |
| BH-FDR survivors at q=0.05 | **54** |

**54 is not 54 discoveries.** `fv_edge_bps` appears in ~15 of the top 25 and
`basis_dir` in ~7, and **both survive alone** (`sign(fv_edge_bps)` 0.4750,
`sign(basis_dir)` 0.4715). An interaction grid re-flagging its own marginals is
the classic artifact. Nearly all survivors sit BELOW 0.5, which — signed
with-my-trade — means anti-predictive.

Re-derive: `python scripts/signal_factory.py --reps 150`
(note: a re-run appends another batch to the ledger; the cumulative count is
report-only and is not the BH denominator, which is the current batch size.)

## 3. Out-of-sample: two of four repeat

Time-ordered split. Both halves sit above `MIN_CI_DAYS`=5, so the
decomposition's own guard does not void the intervals.

| feature | early (15 d) | late (13 d) | repeats? |
|---|---|---|---|
| `fv_edge_bps` | 0.4634 [0.449, 0.485] | 0.4806 [0.469, 0.491] | **yes** |
| `basis_dir` | 0.4496 [0.437, 0.460] | 0.4718 [0.453, 0.488] | **yes** |
| `manip_suspect` | 0.5131 [0.480, 0.555] | 0.4903 [0.463, 0.528] | no — flips |
| `liq_pocket_pull` | 0.5265 [0.419, 0.584] | 0.4334 [0.397, 0.466] | no — flips hard |

The two that survived multiplicity control are the two that replicate.

## 4. AND THEY STILL DIED ON THE COST BAR — the load-bearing result

An AUC is not money. Barriers here are volatility-scaled 8σ:6σ with a cost
floor (`ml.labeling.barrier_geometry`), so break-even P(take-profit) is a
**BAND**, not a point:

```
w_be(sigma) = (sl(sigma) + cost) / (pt(sigma) + sl(sigma))     — decreasing in sigma
  lo = 6/14                = 0.4286   barriers dwarf cost
  hi = (6*4 + 8)/(14*4)    = 0.5714   at the cost floor
```

Held-out half, RESOLVED rows only (n=6,126, 12 day-blocks):

| candidate | rule | P(pt) | day-block CI | verdict |
|---|---|---|---|---|
| `fv_edge_bps` | flip, x<0 | 0.4851 | **[0.4277, 0.5373]** | UNDETERMINED |
| `basis_dir` | flip, x<0 | 0.4709 | [0.4195, 0.5168] | UNDETERMINED |

**The upper CI bound is BELOW the 0.5714 cost-floor break-even.** Real,
replicated, and too small to pay. This is why the cost screen is now inside the
tool rather than left to the reader.

> **A property that is not intuitive and broke this function's first test:** the
> hostile end of the band is **INVARIANT TO THE FEE LEVEL**. At the floor the
> barriers are *defined* as a multiple of cost, so cost cancels. Fees of 5bps or
> 500bps both give 32/56. What a fee rise actually does is push more ROWS onto
> the floor, moving the corpus toward the hostile end. Do not read a stable `hi`
> as evidence that fees do not matter. Pinned in
> `test_the_floor_end_is_INVARIANT_to_the_fee_level`.

## 5. The model knows one of them and ignores the other

From `outputs/meta_model.json` (logistic, standardized):

| feature | weight | \|w\| rank of 64 |
|---|---|---|
| `basis_dir` | −0.220 | **3** — already learned |
| `fv_edge_bps` | −0.0033 | **59** — effectively ignored |

Which is moot, because:

## 6. The champion has NO MEASURABLE SKILL (re-derivation + a baseline correction)

This is a **settled vault fact**, not a discovery — `synthesis/the-money-path-thesis`
already says *"every model rung loses to a constant"*. Re-derived here on a 2.2×
larger corpus, with one correction the page needed.

Deployed selection (`evaluate_and_select` + `cross_fitted_calibrated_oof`),
current corpus 14,915 rows / **12,425 OOF rows** / 18 day-blocks, family
`logistic`:

```
model OOF Brier (calibrated) : 0.248069
BASE  Brier (constant 0.4496): 0.247458
SKILL SCORE 1 - model/base   : -0.0025
paired day-block bootstrap   : 95% CI [-0.0029, +0.0043]
VERDICT: INDISTINGUISHABLE FROM THE CONSTANT  (not "worse than")
```

**The baseline correction.** The thesis page corroborated with *"champion Brier
0.24728 vs **0.25** for a coin"*. That is a **fair-coin** baseline on a label
whose base rate is **0.4496**. The honest constant is `p(1-p)` = **0.247458**.
Against 0.25 the champion appears to win; against its own base rate it does
not. The old comparison was *generous to the model*, so correcting it
**strengthens** the thesis. Callout filed on the page the same session.

**Corroborated by two further independent routes:**
- stored permutation importance (OOS AUC drop): max **+0.0079**
  (`other_ret_6_dir`), **0 of 10** features above 0.01.
- `overfit_check.py` learning curve, same day: **DECLINING**,
  `delta_auc = -0.074` — later rows are HURTING skill.

## 7. THE INSTRUMENT WAS THE FIRST SUSPECT AND THE FIRST SUSPECT WAS MINE

The opening read of this session was **"the model is 2.72% WORSE than the base
rate"**. That number was wrong, and wrong in the direction that made the finding
look bigger.

It divided `oof_brier` — computed on the purged walk-forward OOF **subset**
(`scripts/train_meta.py:379`) — against a constant built from `class_balance`,
which is `y.mean()` over the **FULL training matrix** (`main.py:6734`). **Two
different populations in one ratio.** That is CLAUDE.md reading-discipline (a)
verbatim: a ratio is not a number until its denominator has been read from the
code that computes it.

Both numbers in §6 are computed on one vector, `sel["oof_y"]`.

## 8. What the tests caught that review did not

`tests/test_signal_factory.py`, 20 pins, **all 10 planted mutations verified
RED**. Two were found by mutation, not by reading:

1. **A REAL DEFECT in `rule_win_rate`, minutes old.** It had no `MIN_CI_DAYS`
   floor. A percentile bootstrap over few blocks does not get noisy — it
   **COLLAPSES**: measured 3 blocks → width **0.0170** against **0.0347** at 60
   blocks, i.e. the thinnest evidence produced the MOST confident interval. A
   rule firing on three days could have been reported `CLEARS_COST` on a
   manufactured CI. Now refuses the interval outright and reports `few_blocks`.
2. **A VACUOUS PIN I WROTE.** `test_a_thin_rule_refuses_a_verdict` put all its
   firing rows inside one day, so the new `MIN_CI_DAYS` guard caught them first
   and the pin passed with the row-count guard **deleted**. Rows are now spread
   over 20 blocks so only the row count can produce the refusal.

Also caught, by the repo's own `scripts/instrument_contract.check_self_tests`:
the `--self-test` printed a bare PASS with no measured rate. It now reports its
**33% false-positive rate** on pure-noise controls — which is itself the reason
this module scores against `null_calibration`'s measured chance rate and never
the nominal 5%.

## 9. What this cannot see

- **One corpus, one era.** The OOS split is two halves of ~28 days in a single
  execution era. It is not a regime test.
- **Row-wise transforms only.** No lags, no rolling windows — the corpus is one
  row per signal EVENT across assets, so a time-series transform needs a
  per-asset regrouping this grid does not do.
- **DIRECTION channel only.** Resolution loaders are excluded by construction.
- **No mechanism.** A replicating anti-predictive AUC with no explanation is a
  candidate, not a finding, and nothing here supplies one.
- **The ledger over-counts re-runs** of the same grid on the same corpus. It
  errs strict (a larger reported trial count), and it does not feed BH — the BH
  denominator is the current batch.

## 10. DoD

pytest **4,719 passed** / 16 skipped / 2 xfailed · smoke **220/0** · assurance
**51/0** · overfit **3 ARMED** passed on a live 14,982-row corpus (4 rungs dark,
read the `--` lines) · ruff clean · pyright **0** · bandit 0 issues over 66,538
lines scanned · compileall clean.
