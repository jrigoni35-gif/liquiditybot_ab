# OF-3 PBO breach at 3,651 rows — data-driven, code-inert (finding)

Date: 2026-07-24 · Status: FILED, battery consciously re-baselined at
3 passed / 5 failed (gap[logistic/gbt/mlp] + dof dead-feature + pbo).

## What happened

During Phase A's closing battery (`scripts/overfit_check.py` at
`000e8a3`), OF-3 flipped to FAIL: `pbo=0.56` over 7 configs / 70 splits
on the DEPLOYED simplicity-ladder selection (mean winner gbt_d3_lr10).
The prior conscious baseline (4 passed / 4 failed, 2026-07-23) had PBO
passing one notch under the line with the report's own caveat
"selection has luck in it — expected at this sample size."

## Proof the code delta is inert

The Phase A branch (report-mode conviction formula) touches nothing in
`ml/` or the overfit script. Verified experimentally, not by argument:
`060b217` (last green baseline commit) checked out into a scratch
worktree and run against the CURRENT corpus produced the IDENTICAL
failure — `pbo=0.56`, same winner, same split grid. The shift is
entirely the +23 corpus rows merged at session start (3,628 → 3,651;
3,571 after cleaning).

## Interpretation

At ~3.6k rows the deployed selection rule's luck share crossed 0.5.
This is a learning-health signal, not a trading-risk event: the model
is governor-shadowed (ML-075 L2), so champion selection currently
drives NO live sizing; probes remain throttled by P3 + T4 regime
floors; the evidence-gated selection ladder (#56) already requires OOS
evidence before promotion. The system's existing defenses are exactly
the mitigations this finding calls for — they stay as they are.

## Watch conditions (do NOT widen the gate)

- Re-read PBO at each retrain as live labels accrue (240 live today);
  expected to recover as ground-truth rows displace candidate-proxy
  rows in the selection splits.
- If PBO stays > 0.5 after the next ~100 live labels, revisit the
  config-ladder BREADTH (7 configs may be more selection space than
  3.6k rows affords) — shrink the space, never the gate.
- Any future overfit shift must repeat this doc's inertness experiment
  (base-code × current-corpus in a worktree) before re-baselining.

## Recovery note (2026-07-24, later same day)

At 3,910 corpus rows (+282 candidate rows since the breach) OF-3 PBO
PASSES again — the battery moved 3-passed/5-failed → 4-passed/4-failed
(remaining fails: the known gap[logistic/gbt/mlp] + dead-feature
family). Code-inertness proven per this doc's own protocol before
re-baselining: the entire Phase C3 diff stashed and the check re-run at
clean 5ca57a1 produced the identical result. Conscious baseline is now
4 passed / 4 failed. The watch condition stands: any future shift
repeats the inertness experiment first.

## Second recovery (2026-07-24, evening): 4/4 → 5/3 at 4,049 rows

+139 PC-generated corpus rows moved another gap-family check to PASS.
Inertness proven per protocol: the 4/4-baseline commit (220c290) in a
scratch worktree against the current corpus reproduces the identical
5-passed/3-failed. Conscious baseline is now 5 passed / 3 failed
(remaining: two gap-family + dead-feature). The corpus is healing the
thin-corpus family exactly as growth predicted; the watch condition
stands unchanged.

## Oscillation (2026-07-25, morning): 5/3 → 3/5 at 4,301 rows

+252 rows (drought-era candidates: 92% label-0, sl/time_stop-heavy per
the 07-24/25 barrier mix) flipped PBO back to FAIL (0.53) and re-flagged
gap[logistic] + dead-feature (0.63). Inertness proven per protocol: the
5/3-baseline commit (2a7ac86) in a scratch worktree against the current
corpus reproduces the IDENTICAL 3-passed/5-failed with the same numbers
(pbo=0.53, gaps 0.193/0.252/0.216, dead=0.63) — the triggering diff was
dashboards-only and touches nothing in `ml/`. Reading: at ~4.2k rows the
deployed selection's luck share is OSCILLATING around the 0.5 line
(0.56 → pass → pass → 0.53), and the one-sided candidate inflow from the
entry drought skews the label base rate while live labels sit frozen at
240. Conscious baseline is now 3 passed / 5 failed. The original watch
condition is UPDATED to match its own intent: the "~100 more live
labels" clock cannot advance during the drought, so if PBO still
straddles 0.5 once live labels resume and reach +100 (340 total),
shrink the 7-config ladder BREADTH — never the gate. The drought itself
is adjudicated by the 07-25 floor verdict.

Same-day recovery: at 4,407 rows (+106 fresh PC rows, midday) the
battery is back to 5 passed / 3 failed. Inertness proven per protocol
(1dc43c9 × current corpus in a worktree → identical 5/3; the triggering
diff was a CSS string + two row titles). Conscious baseline: 5/3. This
is the third boundary crossing in ~36 h — treat any single-check flip
inside the {3,4,5}-passed band as the documented oscillation unless the
inertness experiment says otherwise.

Fourth crossing (2026-07-25 evening): 5/3 → 4/4 at 4,633 rows; inertness
proven again (9e3bdd6 × current corpus in a worktree → identical 4/4;
triggering diff was dashboard code-label decode only). Conscious
baseline: 4/4. The oscillation reading stands.

Fifth crossing (2026-07-26, Phase-1 battery for the learnaccel drought
floor): 4/4 -> 5/3 at 4,692 rows (+27 fresh PC rows merged at session
start). Inertness proven again, strongest form yet: cc57019 x current
corpus in a worktree reproduces not just the 5/3 count but md5-identical
per-check verdict lines (all three fails are the OF-1 memorization-gap
checks; PBO 0.07). The triggering diff (SZ-048 drought floor + test/doc
pins, b550b6f..34bb82d) touches probe admission at runtime only — no
corpus, model, or selection code. Conscious baseline: 5/3. The
oscillation reading stands.

Sixth crossing (2026-07-26, Phase-3 measured-headroom branch): 5/3 -> 4/4
at 4,642 rows. Note the corpus is SMALLER than the fifth crossing's
4,692 — not a loss: the raw file grew to 4,722 rows while clash-dedup
absorbed more duplicate candidate/live pairs, so survivors fell. Row
count alone is therefore not a monotone clock; read it with the dedup
stats.

Inertness proven in the strongest form yet: e843b92 (the pre-Phase-3
main) checked out in a worktree and run against TODAY's corpus produces
md5-identical PASS/FAIL verdict lines to HEAD (15bb8b6) —
f68296e3775e3787f3c473c461563a92 on both sides, all eight checks,
including the identical gap trio (0.186/0.224/0.278), pbo=0.23, and
dead_frac=0.60. Phase 3 shipped four instruments (feature-stability
screen, PBO variant axes, monotone GBT rung, loader epoch filter) and
every one of them is inert by construction — flags default off and
`scripts/overfit_check.py` never passes `epoch_cfg`.

The flipped check is OF-7's dead-feature fraction (0.52 -> 0.60, gate
0.55), a SINGLE-POINT reading at seed=7/n_splits=5. Phase 3's T3.1
screen supersedes that view: across 3 seeds x 3 n_splits the same corpus
yields 30-37 dead per combo but only 13 unanimously dead, and the
three-snapshot intersection is 8 — of which only 5 clear the coverage
floor in docs/quant/pbo_admission_policy.md. A single-point dead_frac is
therefore a noisy estimator of the quantity the gate cares about; do not
tune the gate to it. Conscious baseline: 4/4. The {3,4,5}-band
oscillation reading stands, now with six documented crossings.

## Seventh crossing (2026-07-28): 4/4 -> 5 passed / 3 failed

Standing baseline through the entire geometry-alignment feature
(T1-T8, 2026-07-27/28): 5 passed / 3 failed, measured identically on
at least eight independent battery runs. The three fails are the OF-1
gap trio alone (gap[logistic]=+0.198, gap[gbt]=+0.297, gap[mlp]=+0.236
at 4,907 dedup-surviving rows); every other check passes, including
the two that flipped this band upward:

- OF-7 dead_frac recovered 0.60 -> 0.52 (gate 0.55) as the corpus grew
  from 4,642 to 4,907 survivors — consistent with the sixth crossing's
  own caution that a single-point dead_frac is a noisy estimator; the
  band oscillation continues to be corpus-driven, not code-driven.
- OF-3 PBO collapsed 0.23 -> 0.03 over 7 configs / 70 splits (deployed
  simplicity-ladder rule; argmax stress also 0.03) — the healthiest
  PBO reading recorded in this document.

Conscious baseline: 5/3. No gate touched, no threshold moved. The
geometry-alignment feature shipped with this baseline pinned unmoved
across every task battery (see docs/quant/2026-07-28_geometry_
alignment_adjudication.md), so the crossing is attributable to corpus
growth between the sixth crossing's snapshot and this one — the
new-era rows accumulating under the triple-barrier label repair. Seven
documented crossings; the {3,4,5}-band oscillation reading stands.

## Eighth transition (2026-07-28, REGIME CHANGE): era exclusion ACTIVATED
## — the baseline series restarts on the clean corpus

Hours after the seventh crossing was recorded, the 2026-07-28 pc-live
import (611 fresh rows) pushed the new-era (triple_barrier) count to
663 — past ml.era_exclusion.min_new_era_rows=150 — and the era-gated
training exclusion armed and activated exactly as designed (operator
decision 2026-07-26, docs/quant/2026-07-26_era_exclusion.md). From this
point every corpus consumer, overfit_check included, measures the
CLEAN new-era view only.

This is NOT a crossing within the old series — it is the end of that
series. All seven prior crossings measured the mixed-era corpus
(legacy + exit_sim + time_stop + tb); that population no longer exists
for these instruments. New baseline, first reading, 661 rows:

- 3 passed / 4 failed. Fails: the OF-1 gap trio (+0.319/+0.346/+0.438
  — wider than the mixed-era readings, expected: a 661-row corpus
  memorizes more per parameter) and OF-7 dead_frac 0.58 (thin-corpus
  reading, same noisy-estimator caveat as the sixth crossing).
- Passes: shuffle (z=0.6), purge (leak_closed=-0.006), pbo, dof floor
  (rows/feature=10.7, just above the 10 floor — the corpus only barely
  qualifies to be measured at all).

Conscious baseline going forward: 3/4 on the era-excluded view,
expected to IMPROVE as the clean corpus grows (the old series took
~5k rows to reach 5/3). No gate touched, no threshold moved, nothing
compensated. Movement in either direction from here reads against the
new-era corpus size first.
