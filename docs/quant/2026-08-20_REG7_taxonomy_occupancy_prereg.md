# REG-7 (pre-registered 2026-08-20): regime taxonomy vs the market actually present

*Companion to REG-6. Operator directive: "optimize those categories into
what is actually present in the market today." Method discipline:
category lines are drawn from OCCUPANCY AND STRUCTURE (how the market
spends its time), never from the outcome table - fitting regime
boundaries to win rates is textbook OF-4 and is not done here. The
outcome column is reported for honesty and quarantined from the design.*

## Measured occupancy - 12,891 stamped rows, 40 days

| label | all-time | last 7d | inside-label structure |
|---|---:|---:|---|
| range | 56.8% | 25.5% | vol p50 = 16th pct - the everything-bucket |
| bear | 38.0% | 52.4% | vol p50 = 8th pct, momentum mean -0.12 - "bear" is mostly LOW-VOL MILD DRIFT, not falling tape |
| bull_quiet | 4.3% | 17.8% | rising occupancy through August |
| crisis | 0.85% | 4.4% | fired for the FIRST TIME EVER this week - and it was UPWARD |
| bull_volatile | 0.09% | 0.0% | **functionally extinct** (its one-hot is on the dead-feature list for exactly this reason) |

Report-only outcome column (NOT used to draw lines): bull_quiet 0.394,
crisis 0.527 (n=110, one event, the melt-up - REG-6's Tier question in
miniature), bear 0.286, range 0.222.

## The three mismatches with today's market

1. **bull_volatile never happens.** A five-label taxonomy spends a
   stratum, a one-hot feature, and a playbook on a state with 12 rows
   in 40 days. The 2026 majors tape does not produce sustained
   high-vol bull trend; it produces range punctuated by EVENT melt-ups
   (which land in crisis, not bull_volatile).
2. **"bear" over-declares.** 38-52% occupancy with median vol at the
   8th percentile and barely-negative momentum: the classifier reads
   quiet downward drift as bear and blocks longs on it (SZ-022, the
   single largest veto class). The gate-efficacy read shows that block
   mildly healthy (-4.6pp vs baseline) so this is a SEMANTIC and
   STRATIFICATION defect more than a P&L one - but muddy strata poison
   every per-regime statistic downstream.
3. **crisis is direction-blind and, on all recorded evidence, has only
   ever been a melt-UP.** (REG-6, already registered.)

## Proposed taxonomy (boundary adjudication, one decision)

Six labels replacing the current five:

    bull  |  range_quiet  |  range_active  |  drift_down  |  crisis_up  |  crisis_down

- `bull_volatile` retired (extinct; rows fold into bull / crisis_up).
- `range` split at its own vol median into range_quiet / range_active -
  the 57% bucket is doing two jobs (dead tape vs live chop) and every
  consumer (sizing, tier scale, stop mult) plausibly wants them apart.
  Split point = structural (vol tercile of RANGE-stamped rows,
  refreshed at fit time), never outcome-tuned.
- `bear` renamed `drift_down` with its playbook INITIALLY UNCHANGED -
  the honest name for what it measures; a true falling-tape state is
  crisis_down. Any threshold change to its trigger is a separate,
  explicitly-flagged gate change.
- crisis splits per REG-6 (tier decided by the pre-registered
  counterfactual criterion there).

## Costs, named (why this is one boundary decision, not a patch)

- Label-set change = ML one-hot schema change (frozen), postmortem/
  cohort strata change, playbook keys, config_guard checks, dashboards.
- DoF: 6 labels x per-regime stats need coverage; bull_quiet has 4 live
  closes TODAY - splitting range makes thin strata thinner. The
  adjudication must weigh strata legibility against coverage, with the
  learning-symmetry audit's verdict in view (honesty machinery already
  exceeds what the signal pays for).
- Validation rule: the new taxonomy is judged on data OUTSIDE its
  design window (all numbers above are the design window) - occupancy
  stability and strata purity first, outcomes only after a fresh
  accrual period. Never on this corpus.

Batch with REG-6 + the standing docket at the era-4 boundary.
