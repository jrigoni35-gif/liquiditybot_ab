# 2026-09-30 — Calibrated drift monitor + scheduled candle collector (COHORT FORK)

Operator, verbatim: "Execute 1 and 2" — (1) fix the drift monitor, whose alarm
mostly measures consecutive-sample autocorrelation; (2) schedule the candle
collector and close the 5m hole.

**Fork:** `main.py`, `ml/monitor.py`, `ml/calibration.py`, `ml/meta_model.py`
are decision-module code (the monitor decides when retrains are requested).
The fingerprint is re-derived at deploy and recorded in the commit. Hard
invariants 1–7 untouched: nothing here places, sizes or exits an order.

## (1) Drift monitor

**Evidence (in-sample null, raw/2026-09-30_drift_share_in_sample_null.md):**
the training corpus against its own deciles — 300 random rows read 1.4% drift
share; 300 CONSECUTIVE rows (how the live buffer fills) read 18.4% mean /
25.1% p95, 42% of measurable features, with zero real change. 36 of 64 voting
features are degenerate (tied deciles) yet sat in the denominator.

**Discrimination test (real corpus, 200 windows each):**

| | legacy flagged / window | calibrated flagged / window |
|---|---|---|
| alternating days (same weeks, no regime change) | 13.3 | 1.8 |
| the later 30% of time (a regime change possible) | 13.1 | 6.0 |

The legacy line flags ~13 features whether or not anything changed; the
calibrated one flags 1.8 (≈ the 5%-per-feature design rate) vs 6.0 — it
separates a changed period from an unchanged one. Its later-period alarms
name sigma_bar_pct / vol_percentile / spread_bps / depth_log / drawdown_pct:
a volatility/liquidity shift, the thing the alarm exists to see.

**Changes:**
- `ml.calibration.feature_psi_null`: per-feature q95 PSI of consecutive
  300-row windows of the training corpus in SIGNAL-TIME order (seeded).
- Retrain computes it (`_retrain_compute`), saves it in the artifact
  (`feature_psi_null`), and keeps the corpus pair as the drift reference even
  when the challenger is rejected (`_drift_ref`, set before any gate; a
  rejected challenger never saves an artifact).
- `ModelMonitor.check_drift(..., psi_null)`: a feature drifts only beyond
  max(fixed threshold, its own null); share over MEASURABLE features.
  `drift_share_uncalibrated` and `drift_calibrated` published beside it. No
  null anywhere -> legacy behaviour exactly.
- Buffer fed by the SAME event as corpus rows (a real candidate
  registration), not every cycle. Consequence: ~14 registrations/h, so a
  fresh process needs ~7 h to reach drift_min_rows (100) - drift is idle, not
  wrong, in that window.
- Board: the drift tile's description (generator, one line).

Pins: tests/test_drift_calibration.py (16, mutation 9/9 vs green control).

## (2) Candle collector

An S4U scheduled task needs an elevated registration (Register-ScheduledTask:
Access is denied). It now rides `pc_supervisor`'s always-on loop instead:
`scripts/candle_collect.py --once` every 6 h (`LB_CANDLE_COLLECT_SEC`,
`LB_NO_CANDLE_COLLECT`), far inside the ~7.5-day ring. Stamp registered in
tests/conftest.py's redirect list on introduction (the 10th leak-class
instance was exactly this omission). Pins: tests/test_candle_collect_cadence.py.

The 09-07..09-23 hole: Kraken trade-tape backfill (`kraken_trades_backfill.py`,
resumable, 1 call/s) for BTC/ETH/LINK/PAXG, then `tape_to_candles.py
--interval 300` into the kraken 5m lane (first-committed-wins; never
overwrites). Run record: HANDOFF row + vault.
