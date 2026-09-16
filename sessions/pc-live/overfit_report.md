# Overfit audit — 2026-09-16 00:10 UTC

Dataset: SYNTHETIC benchmark (forced) — validating machinery, not market

- **PASS** gap[logistic]: OOF gap within memorization band — train_auc=0.645 oof_auc=0.619 gap=+0.026
- **PASS** gap[gbt]: OOF gap within memorization band — train_auc=0.686 oof_auc=0.605 gap=+0.081
- **PASS** gap[mlp]: OOF gap within memorization band — train_auc=0.704 oof_auc=0.631 gap=+0.074
- **INFO** null-floor[logistic] — OOF Brier 0.2388 vs base-rate constant 0.2499 (base=0.491, n=2130) — BEATS the null
- **INFO** null-floor[gbt] — OOF Brier 0.2423 vs base-rate constant 0.2499 (base=0.491, n=2130) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.2389 vs base-rate constant 0.2499 (base=0.491, n=2130) — BEATS the null
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.04 over 8 configs / 70 splits (mean winner: mlp_small)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.04 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=40.0 (2560 rows / 64 features)
- **INFO** dof EFFECTIVE n — UNAVAILABLE (no label times (sig/res are None) - the SYNTHETIC benchmark carries no signal_history correspondence, so there is no concurrency to measure here; this is the expected reading on that corpus, not a defect) — OF-7's rows/feature above is NOMINAL and unqualified
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 6/64 features (58 of the 59 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (synthetic — informational) — dead_frac=0.92 (59 near-zero-importance features) — expected: benchmark plants signal in ~6/36
- **INFO** dof note — low/zero-importance: ['direction', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=1/n null fallback)
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample — dsr=0.003 sr=-0.29 n=33 sr0=0.241 (probes excluded: 417)
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR(SR*=0)=0.067 -> P(true SR < 0)=0.933. This, NOT the graded dsr, is the 'is the edge positive' number - dsr is P(true SR > sr0) where sr0 is the expected max under the null across N trials. A red dsr beside a PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: 33 conviction trips spanning 2026-07-20..2026-09-15 (57.1 days). NOT era-scoped: signal_history.csv has no exec_era column (the stamp lives in core/fill_ledger.py, keyed by position_id), so this sample pools every execution era it covers - different fee bookings AND different barrier geometries. CLAUDE.md: trips are 'citable AS their era, none poolable across a cut'. Read the verdict against THIS span, not against the deployed config.
- **INFO** dsr: deployed-era regression sentinel — DEFERRED - 3 conviction trips wholly inside era 12-10d4d0c2 < 10. The deployed configuration is not yet separately measurable; OF-5's pooled verdict says NOTHING about it either way. [19 conviction trip(s) EXCLUDED (impure_era=19); $-18.91 of PnL is not in this statistic - an exclusion that removes losers is itself a silencing channel, so read this count]
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic — SYNTHETIC benchmark dataset — candidate/live split & base rate n/a (no signal_history.csv correspondence); OOF numbers below validate the machinery on the planted-signal benchmark, not a market read
- **INFO** regime[bull_quiet] oof — oof_n=1097 auc=0.629 (pooled 0.605, delta_auc=+0.024) brier=0.2387 (pooled 0.2423, delta_brier=-0.0036)
- **INFO** regime[unknown] oof — oof_n=1033 auc=0.579 (pooled 0.605, delta_auc=-0.026) brier=0.2461 (pooled 0.2423, delta_brier=+0.0038)
- **INFO** learning curve — SYNTHETIC benchmark dataset — corpus-size trend has no market meaning; skipped
- **INFO** extras liveness — SYNTHETIC benchmark dataset — feed liveness has no meaning; skipped

7 passed, 1 failed (37s)

Corpus: SYNTHETIC benchmark (forced) — validating machinery, not market

> **This green validates the OVERFIT MACHINERY, not the market.** It is not evidence that the deployed strategy is un-overfit.
