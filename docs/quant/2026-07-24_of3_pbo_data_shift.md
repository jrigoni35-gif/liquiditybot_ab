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
