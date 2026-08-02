# Multi-timeframe learning funnel — design

**Date:** 2026-08-01 · **Status:** DESIGN, nothing shipped
**Operator decision it serves:** 1.5-day (432-bar) swing horizon
**Evidence base:** `outputs/horizon_shadow.csv`, 23,799 rows already recorded

---

## The problem this solves

The horizon decision forces a trade the operator should not have to make:

| | 24 bars (2h) | 432 bars (36h) |
|---|---|---|
| barrier / horizon-sigma | 4.07 (deep tail) | **0.96** (literature band) |
| labels produced | fast | **~18x slower** |
| resolution rate | 31.3% | (extrapolated >75%) |

Short horizons give volume and no information. Long horizons give
information and no volume. A corpus that has been starving cannot simply
accept an 18x slowdown, and a model cannot learn from 98.9% time-outs.

The funnel takes both: **volume from short horizons, ground truth from the
long one**, without letting the short ones vote on money.

## Measured basis (the bot's own shadow recorder)

```
horizon      n    label=1  time-out  resolved   mean_net_ret
6b  (30m)  1327     6.2%     98.9%      1.1%       -0.562%
12b (1h)   1327    12.3%     96.1%      3.9%       -0.554%
24b (2h)   7933    16.2%     68.7%     31.3%       -0.554%
48b (4h)   6606    23.7%     43.2%     56.8%       -0.555%
96b (8h)   6606    28.3%     25.0%     75.0%       -0.582%
```

Two readings, both load-bearing:

1. **Resolution is monotone in horizon.** A 30-minute label is 98.9%
   vertical-barrier — it carries almost no information about direction, only
   about elapsed time. Anything below ~24 bars is not a trading label.
2. **Mean net return is FLAT at ~-0.55% across every horizon**, and the
   round-trip cost is ~0.50%. Gross alpha is approximately zero at every
   timescale from 30 minutes to 8 hours. **Lengthening the horizon repairs
   the LABEL; it does not create EDGE.** This design must not be sold as a
   profitability fix. It is a precondition for learning, nothing more.

`P(PT | resolved)` by horizon: 24b 40.8%, 48b 42.6%, 96b 42.0% — all close
to the driftless gambler's-ruin value of 42.9% for these barrier distances.
At longer horizons the labeled bet behaves like a fair weighted coin, not an
anti-predictive one.

## Architecture

```
  price path ──┬─> H_aux1 (24b)  ─┐
               ├─> H_aux2 (96b)  ─┼─> concurrency-aware  ─> weighted ─> model
               └─> H_prim (432b) ─┘   uniqueness (spans      corpus     (multi-head)
                     │                 ALL horizons)
                     └────────────────────────────────> traded bracket
                                                        (PRIMARY ONLY)
```

### R1 — Only the primary horizon may drive a trade

`barrier_geometry()` for the live bracket is computed at `H_prim` and
nowhere else. Auxiliary horizons are training signal only. This preserves
the invariant the geometry-alignment work established (2026-07-27): the
label's bet and the traded bet are the same bet. An auxiliary horizon that
could open a position would break it silently.

### R2 — Auxiliary horizons are AUXILIARY TASKS, not extra rows

The naive funnel appends every horizon's label as another training row. That
is wrong, and wrong in the direction that fools the evidence gate: three
labels on the same signal at the same instant are approximately **one fact**,
not three. Pooling them inflates row count 3x, inflates Kish ESS, and admits
a higher-capacity model family on evidence that does not exist.

Two admissible shapes:

- **(a) Multi-head, shared trunk.** One row per signal; the primary label is
  the decision output, auxiliary labels are extra heads with their own loss,
  down-weighted. Standard auxiliary-task learning. Row count unchanged.
- **(b) Pooled with horizon as a feature + cross-horizon uniqueness.** Rows
  pooled, `horizon_bars` becomes a feature, and the uniqueness computation
  spans horizons so overlapping labels share weight mass.

**(a) is preferred** because it cannot corrupt the row count the evidence
gate reads. (b) is implementable within the existing sample-weight machinery
but every consumer of `rows`/`live_clean` must then be audited.

### R3 — Cross-horizon uniqueness is the load-bearing correction

`ml/history.py`'s average-uniqueness already computes per-(asset, grid-bar)
concurrency over each row's `[signal_ts, ts]` lifespan. Under multi-horizon
that span differs per horizon on the SAME signal, so the concurrency map
must key on the underlying **path**, not the row. Without this the funnel
silently manufactures effective sample size.

This is the single highest-risk piece. It is also where the existing
`ess_kish` / `mean_uniqueness` telemetry already lives, so the correction is
measurable the moment it lands.

### R4 — The evidence gate counts PRIMARY rows only

`live_clean`, `rows`, and `ml.model_selection.min_total_rows` must resolve
against primary-horizon rows. Auxiliary volume must never unlock a model
family. Concretely: `last_load_stats["live_clean"]` counts
`label_era == triple_barrier_h<H_prim>` and nothing else.

### R5 — Era tagging extends, it does not fork

`triple_barrier_era(max_bars)` already stamps `triple_barrier_h{mb}`. Each
horizon gets its own era tag for free. The era-exclusion filter keeps the
CURRENT primary era (fixed 2026-07-31 in b459a90); auxiliary eras must be
explicitly admitted as auxiliary, not silently swept in as "old era".

## Staged implementation

| stage | scope | risk |
|---|---|---|
| **S1** | Report-only: extend `horizon_shadow` to the primary horizon; publish resolution/uniqueness per horizon | none — no training path touched |
| **S2** | Cross-horizon concurrency in the uniqueness map (R3), report-only delta on `ess_kish` | low — telemetry first |
| **S3** | Multi-head model (R2a) behind `ml.multi_horizon.train: false`, shadow-scored | medium — model shape |
| **S4** | Flip to live after the shadow head beats the single-horizon champion on the SAME bar the evidence gate uses | gated |

S1 and S2 are pure measurement and should land before any model change.
Nothing here alters the traded bracket until S4, which is an operator flip.

## What this design refuses to claim

- It does not create alpha. The flat -0.55% across horizons says the entry
  signal has ~zero gross edge today; better labels are a precondition for
  finding one, not a substitute.
- It does not justify shortening the primary horizon back below the
  cost-clearing point. Auxiliary horizons exist to feed learning, not to
  re-legitimise 2-hour trading.
- It does not change `max_concurrent_positions`. At 36-hour holds, slot
  count becomes the binding constraint on primary label throughput; that is
  a separate, deliberate decision.
