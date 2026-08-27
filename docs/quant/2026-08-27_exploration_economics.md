# Exploration economics — cost structure, budget variance, and forecast
**2026-08-27 · financial-analyst pass on the probe engine and the fee line ·
SAFE/report-only**

Prepared for the standing operator questions: *what does the 0.437%
pure-cost drag (fee blindness) and the 89%-probe audit census mean in
dollars, against budget, and forward?* Rates from
`docs/quant/2026-08-26_why_losing_deep_dive.md` (WHY-1, n=54 cohort);
dollar segment splits DERIVED here as rate × median ticket × n and
cross-checked against WHY-1's totals (fee-true xcheck $13.59 ✓, probe
tuition/trip $0.189 vs the doc's ~$0.19 ✓). Re-derive after more fills:
`scripts/cohort_eval.py`, `scripts/cost_attribution.py`.

## Executive summary

The program runs two businesses on one book: a **conviction business**
(5 trips) that is profitable at TRUE venue costs, and a **label-buying
R&D operation** (49 trips, 91% of volume, ~84% of booked fee spend,
~89% of all audit dispositions) whose product — training labels — was
priced against a fee schedule understated by ×1.979. R&D spend is
INSIDE its governor budget (72% of cap even at true fees); the defect
is unit-economic, not overspend: each probe's expected value was
computed against half the real cost, so 49 trades ran whose gross
ceiling (+0.283%/trip) sits below even the booked round trip. The fee
line's budget-to-actual variance (booked $6.87 vs true $13.59,
**+$6.73 UNFAVORABLE, ×1.979**) flips the cohort's operating result
from +$1.36 to −$5.36 and is 100% explained (FEE-1), conditional on
one unverified input: the account's actual tier row (FEE-3, one
read-only `TradeVolume` call).

## 1. Cost structure (era-4 cohort, 16.1-day window)

| line | booked | true (×1.979) |
|---|---:|---:|
| gross trading edge | +$8.23 | +$8.23 |
| venue fees | $6.87 (83% of gross) | $13.59 (165% of gross) |
| **operating result** | **+$1.36** | **−$5.36** |

Segment split (DERIVED: rate × $18 median probe ticket; conviction =
residual, implied avg ticket ≈ $54):

| segment | n | net/trip | segment $ booked | segment $ true |
|---|---:|---:|---:|---:|
| conviction | 5 | +2.132% / +1.463% | ≈ +$4.82 | ≈ **+$3.92** |
| probe (R&D) | 49 | −0.392% / −1.052% | ≈ −$3.46 | ≈ **−$9.28** |

Caveats that bound every number above: conviction n=5 is directional
only (WHY-1 claim 2b: d=1.03 but p=0.062, needs ~16 trips for power);
probe tuition at true fees is the one resolved claim (p≈0.027 after
×1.58 concurrency deflation); effective n is 21.5 of 54 — the book
paid 54 tuitions for ~21 independent lessons.

## 2. Budget variance (favorable / unfavorable)

| line | budget | actual | variance | class |
|---|---|---|---|---|
| fee schedule | 25/40 bps (config) | 40/80 bps (venue T1) | fee line +$6.73/cohort, ×1.979 | **UNFAVORABLE — structural**, 100% explained (FEE-1); conditional on FEE-3 tier verification |
| exploration tuition | governor cap 0.1% equity/day ≈ $0.80/day ($12.88/window) | booked $0.215/day (27% of cap); true $0.576/day (**72% of cap**) | within budget both ways | **IN-BUDGET** — the governor did its job; the defect is unit pricing, not volume |
| probe unit EV | each probe admitted with EV ≥ 0 at booked fees | gross +0.283%/trip vs 0.65% booked / ~1.29% true round trip | every probe's ceiling below cost | **UNFAVORABLE — mispriced tuition** (WHY-1 #2); fix staged (p_win 0.85, bar 0.8335) |
| timeout churn | — | 19% of trips exit `tb_time`, −0.624%/trip (deflated p≈0.07) | semi-mechanical fee churn | WATCH — the actionable number is the 19% rate |
| asset mix | — | alt tail −$3.67 booked on 27 trips | — | **NOT CLASSIFIED** — grouping chosen post-hoc (deflated p≈0.08); pre-register before acting |

## 3. Unit economics of information (what the tuition buys)

| unit | booked | true |
|---|---:|---:|
| cost per closed probe label | $0.071 | **$0.189** |
| cost per INDEPENDENT lesson (n_eff-adjusted) | $0.178 | **$0.476** |

At 3.4 closes/day the flywheel buys ~3 labels/day for ~$0.58/day true.
Whether that is worth paying is, post-fee-truth, a **conscious learning
budget, not a leak** (WHY-1 #2) — the price list is now on the table.

## 4. Rolling forecast (driver-based; drivers: pace 3.43 closes/day,
mix 91/9, tickets $18/$54, per-trip rates above)

- **Base (mix unchanged, accrual continues to n=100 — only if the
  operator elects continuation; the SIGNED COST_BOUND arm is 2D):**
  ~13.4 more days; +42 probes / +4 conviction; incremental net ≈
  +$1.64 booked / **−$4.79 true**; cumulative at n=100 ≈ +$3.00 booked
  / **−$10.15 true**. Intervals dwarf these points (n_eff ≈ 21 today);
  read as direction, not targets.
- **Fee-truth scenario (arm 2D + staged boundary package applies):**
  entry bar 0.690 → 0.834 (FEE-2) ⇒ the probe lane stops clearing BY
  CONSTRUCTION. Tuition spend → ≈$0; label acquisition from probes →
  ≈0/day; the book becomes 100% conviction-lane (fewer, larger — and
  after ALGO-5, wider). The financial meaning of the cut: the R&D
  department is closed at the old price and must be re-opened, if at
  all, at a deliberately budgeted one.
- **Bear:** a regime suppression episode (crisis pin, SD-003-class
  throttle) cuts pace; the window stretches, fixed-cost time passes,
  totals barely move (the book is small; time, not dollars, is the
  cost).

Forecast-accuracy note: the skill's ±5% target is not meaningful at
n_eff ≈ 21; this forecast is for ORDERING decisions (booked-vs-true
sign flip, tuition price list), not for point tracking.

## 5. Follow-up hooks

- FEE-3: verify the tier row (one read-only `TradeVolume` call, first
  credential on the box) — every "true" number above is conditional on
  it.
- Re-run this decomposition at the readout adjudication and after any
  boundary cut lands (`cohort_eval.py` + this doc's derivations).
- Registry entries carrying these issues: TH-R-012 (fee blindness),
  TH-R-013 (overtrading/action bias) in `docs/thales/REGISTRY.md`.
