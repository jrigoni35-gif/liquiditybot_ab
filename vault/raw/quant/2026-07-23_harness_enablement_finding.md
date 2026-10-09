# Quant-trials harness enablement finding (#103 T6, 2026-07-23)

**Decision: enablement REVERTED, deferral conscious.** The G1 failure below is
a stop-and-report finding (CLAUDE.md: never widen a gate), adjudicated by the
coordinator with operator sign-off ("do it how Anthropic would"): the harness
stays on the pre-P1/P2 geometry (its long-green baseline), the deployed
cost-floor question goes to the REAL experiment — the paper-telemetry review
armed for 2026-07-25T19:44Z — and re-enablement is blocked until the floor
question is resolved on live data. The enablement diff is preserved verbatim
below so re-running the experiment is a paste away.

## What was measured

`scripts/quant_trials.py` was locally modified (never committed) to mirror
config.json's shipped `profit_taking` block: `min_trigger_cost_mult: 3.0`
with the harness Position carrying `est_cost_bps = 40.0` (derived from the
harness's own per-side cost model: entry leg + exit leg + spread as charged
by `run_arm`), and `time_stop: {enabled: true, max_bars_no_progress: 36,
min_mfe_frac_of_tier1: 0.5}`. Seeds, trial count (200×1200), gate math and
printing unchanged. Runs deterministic (two identical full-scale runs).

## Results (200×1200, seed 7)

BASELINE (committed harness, f6cdbe3 — neither lever):

    ok    G1 tail drawdown   p95 4.76% vs cap 5.53%
    ok    G2 tail outcome    CVaR5 -4.57% vs -6.17%
    ok    G3 upside intact   median -1.37% vs floor -2.17%
    ok    G4 ruin rate       0.00% vs 0.00%
    ok    G5 capture         0.55 vs 0.53
    ALL GATES PASS

ENABLED (deployed geometry — both levers):

    FAIL  G1 tail drawdown   p95 4.85% vs cap 4.66%
    ok    G2 tail outcome    CVaR5 -4.67% vs -5.72%
    ok    G3 upside intact   median -1.44% vs floor -1.86%
    ok    G4 ruin rate       0.00% vs 0.00%
    ok    G5 capture         0.50 vs 0.43
    GATE FAILURE

Ablations (diagnostic-only, same scale/seed):

    cost-floor ONLY:  FAIL G1 (p95 4.71% vs cap 4.43%); G2/G3/G4/G5 ok
    time-stop ONLY:   ok   G1 (p95 3.45% vs cap 3.87%) — strictly
                      gate-positive on every metric

## Mechanism

- The cost floor raises tier-1's effective trigger in the harness world from
  1.0% (legacy) to 1.2% (3.0 × 40 bps): partial-take de-risking is delayed,
  so protocol-arm paths breathe deeper before banking — the p95 drawdown
  tail worsens both alone and combined. Classic cost of raising a
  partial-take trigger on a mediocre signal.
- The two levers are COUPLED, not additive: `_time_stop_hit` computes its
  scratch threshold from the SAME `_tier_trigger_pct(tier_index=0,
  est_cost_bps=...)` the floor raises, so enabling both lifts the scratch
  bar from 0.5% to 0.6% MFE and scratches a wider band (including 0.5–0.6%
  MFE trades the time-stop alone would ride). Combined drawdown (5.48%
  protocol-arm dd) is worse than either lever alone (5.21% / 4.55%).

## Why this does NOT immediately indict the live config

The harness's synthetic cost stack is 40 bps/side-class, so its floor
(1.2%) binds ABOVE the 1.0% trigger — always. The live measured stack is
~20.5 bps → floor 0.615% vs a 1.0% legacy trigger: the live floor binds
only where the VOL-CLAMPED trigger falls below 0.615% (low-vol regimes).
The harness therefore overstates the floor's bite; it identifies a real
directional risk (floors delay de-risking → deeper drawdown tails) whose
LIVE magnitude is an empirical question the paper run answers directly.

## What the paper review must check (wired into the 48h telemetry check)

1. Drawdown depth / MAE on positions that never bank tier-1 (the floor's
   delayed-de-risk cost, the G1 mechanism, at the live floor's real bite).
2. Share of closes where the floor actually bound (low-vol entries) and
   their P&L shape vs non-bound closes.
3. Scratch band: MFE distribution of PT-060 scratches — are 0.5–0.6%-of-
   trigger MFE trades being scratched (the coupling cost) or only true
   no-progress trades?

If the live data confirms the harness's direction at material size, the fix
is a conscious re-derivation of the floor (e.g. cap the floor at the legacy
trigger, or lower `min_trigger_cost_mult`) — never a gate widen — after
which the harness enablement below is re-run and G1–G5 re-baselined at
200×1200.

## The preserved enablement diff

The full uncommitted diff, est_cost_bps derivation, bar-clock mapping, both
verbatim runs and the small-N CI-pin margin analysis are archived in the
session ledger (`.superpowers/sdd/task-t6a-report.md`, session scratch) and
reproduced in essentials here. To re-run: give the harness Position
`est_cost_bps=EST_COST_BPS` (derived from the harness cost model), add
`min_trigger_cost_mult` + the `time_stop` block to `TIER_CFG` mirroring
config.json verbatim, and map the trial's bar step to the engine's
`now`-based `bars_in_trade` (one trial step = one 5m bar).

Note for future re-baseline: `tests/test_quant_trials.py`'s small-N
(80×1000) CI pin remained green under enablement but with its G1 margin
collapsed ~10% → ~1% — the small-N pin is NOT a reliable early-warning for
full-scale G1 movement; re-baseline at 200×1200 only.
