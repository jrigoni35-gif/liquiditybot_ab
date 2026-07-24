# Profit goals & mindset review — all timeframes (#121)

Date: 2026-07-24 · Financial-analyst read-only assessment; every figure
cited to source. Live snapshot: origin/paper-telemetry
control/pc_status.json @ 2026-07-24T03:26:57Z, cycle=78 since restart
(process-local counters reset at that boundary), cycle_lifetime=136838.

## 1. Timeframe map

| Horizon | Goal (source) | Realized (source) | Verdict |
|---|---|---|---|
| Intra-day (5m) | none configured — goals machinery covers week/month only (core/goals.py; config.json:174-176) | daily_pnl 0.0 (day-boundary reset, uninformative this early) | NO-DATA — scope gap, not a measurement gap (§6) |
| Weekly (RP-070) | weekly_profit_goal_usd: 25 (~0.5% of $5k) | weekly_pnl −17.15, attainment 0.0%, ~4/7 days elapsed (W30) | UNFAVORABLE — loss, not shortfall |
| Monthly (RP-071) | monthly_profit_goal_usd: 110 (~2.2%) | monthly_pnl −16.88, attainment 0.0%, 24/31 days | UNFAVORABLE — loss, not shortfall |
| Trailing 200 trades (perf window, implicit PF>1) | expectancy>0 | trades 200, win_rate 0.10, PF 0.044, expectancy −$0.1649, net −$32.99 | UNFAVORABLE (window is regime-MIXED, see reconciliation note) |
| Cycle-scale long book (Phase C) | evidence ladder 10/20/30% (spec §4-5) | not shipped (no code, correctly per sequencing) | NO-DATA |

Account level: equity $4,965.86 (cash 4,964.87 + savings 0.74 + reserve
0.25), drawdown 0.69%, fees_total 34.54, realized_total −19.9.

Equity history (sessions/pc-live/equity.csv, 70,976 rows): three capital
eras ($25k start 07-10; $100k spike→$800 crash 07-12; reset to $5,000
2026-07-16T21:37:36 via scripts/reset_paper_capital.py). Current stable
era: 7.21 days, $5,000.00 → $4,965.86 (min 4,965.72), net −$34.14.

OPEN RECONCILIATION ITEM (flagged, not silently resolved):
realized_total (−19.9) vs equity-era net (−34.14) vs 200-trade net
(−32.99) do not reconcile — reset_paper_capital.py zeroes realized/fee
totals (scripts/reset_paper_capital.py:43-45) but the 200-trade
PerformanceTracker window is trade-count-based and spans the pre-reset
$800 era.

## 2. Variance analysis (F/U with root cause)

- Weekly/monthly misses [U]: week-to-date realized loss; category
  "loss" per core/goals.py:53-54. Monthly −16.88 vs weekly −17.15 ⇒
  pre-week July was ~+$0.27 — THIS WEEK's losses drive the monthly miss.
- PF 0.044 (avg win $0.076 vs avg loss $0.192, payoff 0.394) [U]:
  monitor.causes attributes 155/201 graded closes (~77%) to plain
  UNDERPERFORMANCE, 37 cost_overrun, 6 alpha_wrong, 2 regime_shift,
  1 whipsaw. Cost overrun is real but minority; champion_brier 0.1901
  ≈ coin-flip — the signal mostly just didn't work.
- Governor at L2 KILL SWITCH (use_model false, kelly 0.4, shrinkage
  0.7) [U, structural, EXPECTED]: the governor doing its job on a
  no-edge-yet model at 3,721 rows / 240 live labels.
- OF-3 PBO 0.56 [U, data-driven]: proven code-inert
  (docs/quant/2026-07-24_of3_pbo_data_shift.md); zero live sizing rides
  on champion selection today.
- SZ-047 throttle, 16 denials since restart [MIXED]: correctly
  suppresses net-negative probe flow (P3 derivation) BUT slows live-
  label accrual → bear regime still 4/60 live labels → conviction's
  regime-known term can't admit bear conviction → governor shadowed
  longer. The SZ-047 → labels → governor chain is real and quantified.
- Conviction formula: evaluated 0 / admitted 0 this restart [NO-DATA]:
  cadence windows are process-local by design; silence until
  share_min_n=20 fresh samples.
- Harness G1 failure (cost-floor + time-stop) [U, PENDING]: p95 4.85%
  vs cap 4.66% at 200×1200; live verdict armed 2026-07-25T19:44Z.
- Weekly loss budget: 10.6% consumed of 6%; dd_throttle_mult 0.9325
  engaged [F, contained] — preservation stack working as designed.
- PT-060 count [NO-DATA]: absent from code_stats top-15 this restart
  (counter resets at process start); says nothing about the full week.
- LOCAL LEDGER CONTAMINATION (process finding): outputs/weekly_ledger
  .csv and monthly_ledger.csv are contaminated by local pytest/smoke
  runs writing the default output path with a synthetic $10k account
  (every row cash=10000.0, goal=0.0, untracked). DO NOT use local
  ledger CSVs for goal-vs-actual; authoritative source is
  control/pc_status.json status.goals. Follow-up process fix warranted.

## 3. Mindset audit — five principles vs observed behavior

1. Preservation is the root — ✅ EMBODIED: throttle 0.9325, L2 kelly
   0.4, LTC circuit breaker tripped (2.41h), 10.6% budget used. Most
   mature principle in the telemetry.
2. Evidence buys size — ⚠️ PARTIAL: mechanisms shipped (conviction
   regime-known term, T4 floor) but bear evidence is scarce (4/60) and
   zero conviction evaluations this restart. The demand for evidence is
   correct; the evidence is still accruing.
3. Context before conviction — ⚠️ DESIGNED, NOT LIVE: context term
   auto-passes (None) until Phase B ships. By design, not violation.
4. One truth ledger — ✅ mostly (hash-chained audit, RP-070/071);
   GAP: local dev-env ledger contamination (above) — a real one-truth
   violation at the local level, process fix flagged.
5. The corpus is the asset — ✅ EMBODIED: 3,721 rows; OF-3 FAIL filed
   honestly rather than gate-adjusted; REJECTED-list discipline (11+
   killed entries with citations).

## 4. Max-net-profit levers, ranked

1. RESOLVE THE HARNESS G1 FINDING ON LIVE DATA (armed 25T19:44Z).
   Decision tree: live MAE/drawdown on non-tier-1-banking positions
   confirms harness → re-derive floor consciously (cap at legacy
   trigger or lower mult) → re-run harness → re-baseline G1-G5;
   not confirmed → re-enable harness at current geometry. Disqualifier:
   widening G1's cap.
2. CONVICTION ENFORCE-FLIP: positive only if report telemetry shows
   denials correlate with the underperformance bucket. Preconditions:
   ≥20 evaluations in-window (currently 0) + re-derived
   agreement_floor/ev_cost_mult from the REPORTED distribution + green
   200×1200. Disqualifier: flipping early or deriving from a backtest.
3. BEAR REGIME COVERAGE (4/60 live labels): unblocks conviction sizing
   + governor recovery as labels accrue. Disqualifier: ANY manual
   floor override to force bear conviction.
4. PROBE-SHARE TUNING: only via a fresh P&L-by-admission-channel
   diagnosis (same methodology as the 07-23 derivation). Disqualifier:
   tuning to what-would-have-looked-better (OF-4).
5. LONG-BOOK ACTIVATION: nothing to activate until Phase B ships the
   context engine ("unknown" must exist and block adds first).
6. MODEL REHABILITATION: ML-075 shadow-recovery path only
   (3 consecutive healthy windows); never a manual kill-switch
   override, never loosened Brier margins.

## 5. Scenario forecasts (30/90/365d @ ~$4,966)

Grounding rates DISAGREE 6×: weekly-era ≈ −$4.29/day vs monthly-era
≈ −$0.70/day; the 200-trade expectancy (−$0.1649/trade) is regime-mixed
and pre-dates P1/P2 by design. That disagreement IS the finding: the
sample is too thin/mixed for a point forecast.

- BEAR (−$4.29/day persists): 30d ≈ −$129 (→ ~$4,837); 90d ≈ −$386 —
  in practice the risk stack (daily 5%, weekly 6%, hard stop 15%:
  config.json:180,229,230) trips and de-risks long before such depths.
- BASE (−$0.70/day): 30d ≈ −$21; 90d ≈ −$63; 365d ≈ −$255 —
  ILLUSTRATIVE ARITHMETIC ONLY (linear extension of a 24-day shadowed,
  pre-fix-dominated sample).
- BULL (P1/P2 + governor recovery net-positive): INSUFFICIENT SAMPLE —
  0 conviction evaluations, harness verdict pending.

Do not size capital against the 90/365d columns. The one actionable
number: at current burn the preservation invariants trip well before
capital impairment — the design working as intended.

## 6. Goal recalibration

- weekly 25 / monthly 110: KEEP (measurement-only targets; changing on
  a losing sample = tuning the ruler to the miss).
- Daily goal: real SCOPE GAP — add only if operator wants it; small
  config-lifted extension of core/goals.py's pattern; no number
  recommended (no realized daily distribution derived yet).
- min_trigger_cost_mult 3.0 + time_stop 36 bars: KEEP pending the 48h
  live verdict (coupled levers; changing one re-runs untested coupling).
- regime_floor_live 60: KEEP (300/5 derivation on record; bear at 4).
- conviction.mode report: KEEP (enforce criteria unmet by definition).
- max_probe_share 0.35: KEEP (fresh 07-23 data derivation; no new
  channel diagnosis since).

## Executive summary

Live paper equity $4,965.86, −$34.14 over the 7.2-day capital era.
Weekly (−17.15 vs +25) and monthly (−16.88 vs +110) at 0% attainment,
categorized loss-not-shortfall. Dominant root cause: plain
underperformance (155/201 closes) with minority cost overrun (37/201);
champion Brier 0.19 ≈ coin-flip, governor correctly at L2 with no live
sizing on the model. Preservation stack is the healthiest subsystem
(~11% of weekly loss budget used). Single most consequential open item:
the harness G1 verdict armed 2026-07-25T19:44Z — no lever moves before
it resolves. Conviction enforce-flip and Phase C are both not-ready by
their own stated preconditions. Forecasts honestly wide (grounding
rates disagree 6×) — 90/365d figures are arithmetic, not sizing
guidance. No goal recalibration is data-justified today except
optionally ADDING a daily target (scope gap, operator's call).
