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
