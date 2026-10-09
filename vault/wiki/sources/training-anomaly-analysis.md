---
title: Training Anomaly Analysis (2026-07-29)
category: source
summary: Six dashboard anomalies root-caused, revealing one systemic thread: era exclusion activated and broke three downstream consumers never re-baselined for it
tags: [era-exclusion, deadlock, anomalies, governor]
sources: 1
updated: 2026-08-01
---

# Training Anomaly Analysis (2026-07-29)

**Raw source:** `raw/quant/2026-07-29_training_anomaly_analysis.md`

## The one systemic thread
Era exclusion activated on 07-26/27 and **broke three downstream consumers that were never
re-baselined for it**, including a structural deploy deadlock.

## The six anomalies
1. **CLEAN LIVE LABELS: 0** — exclusion is ACTIVE (1,516 tb rows >= 150) and **all 253 live rows are
   old-era**. `live_clean` is the post-exclusion count, so 0 is the true number. *Expected, with a
   real residual gap.*
2. **1b: why still no live `tb_*`** — `bracket_exits` only enabled 2026-07-28 01:24; the few closes
   since were long-book or senior/realize paths; plus a VOI-fastpath defect realized a 2h-old bracket
   as `realized`. Class: *real defect, partially fixed, unverified on the live box.* This optimism is
   refuted two days later by [[sources/live-label-era-deadlock]].
3. **LABEL UNIQUENESS 0.159** — genuine window overlap, not duplicate flooding. Exact feature-row
   duplicates only 1.1%; median label lifespan 38 bars (~3.2h) with per-cycle registration => ~6
   concurrent labels per (asset, bar). Corrections already run.
4. **RETRAIN: QUEUED persists — the deploy deadlock.** The flag clears only on `note_deployed`, and
   deploys are **structurally impossible**: champion `blend` was trained pre-exclusion on 4,823 rows
   while the post-exclusion matrix is 1,516, so `oof_idx >= trained_rows` is empty, the rescore
   returns None, and the like-for-like gate REJECTs fail-closed every retrain. **Bonus lock**: with
   `live_clean=0` the evidence gate admits only `logistic`. See [[concepts/deploy-deadlock]].
5. **WR 9.5%, PF 0.05; DOGE/DOT 12-loss streaks** — SZ-046 fires (4 losses -> 6h veto) but its
   cooldown **auto-resets the streak**, making it a **rate limiter** (~4 losses/6h/asset), which is
   how a ledger streak reaches 11-12. **No per-asset win-rate-aware probe decay exists**; the
   "regime-aware probe decay" that shipped pins probe epsilon at 1.0 for under-covered regimes, i.e.
   MORE probes.
6. **ARB stop-zone 1.00 / FLOW manip 0.72 yet both still trade** — three deliberate layers: THALES in
   shadow; probe `p_win` floored at 0.70 after any shade; the manip gate biting only as a downsize.

## Key reproduction
`load_training_data(era_cfg=config)` -> rows **1,516**, live_clean **0**, mean_uniqueness 0.1581,
excluded **4,856 rows** (all 248 in-scope live rows among them). Per-era label rates: legacy 0.261 /
exit_sim 0.134 / time_stop 0.0066 / triple_barrier 0.302. Champion `blend`: rows 4,823, oof_brier
0.1237, class_balance **0.169** vs post-exclusion base rate **0.30**.

## Shipped
ML-083 era-orphan clause (later found ineffective and repaired in
[[sources/correction-verification]]); calibration-gap `no_value` text corrected on four panels.
