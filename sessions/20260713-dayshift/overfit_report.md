# Overfit audit — 2026-07-13 19:44 UTC

Dataset: SYNTHETIC benchmark (live rows=0 < 460) — validating machinery, not market

- **PASS** gap[logistic]: OOF gap within memorization band — train_auc=0.636 oof_auc=0.627 gap=+0.009
- **PASS** gap[gbt]: OOF gap within memorization band — train_auc=0.653 oof_auc=0.602 gap=+0.052
- **PASS** gap[mlp]: OOF gap within memorization band — train_auc=0.676 oof_auc=0.633 gap=+0.044
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.3 (limit 3.0)
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.20 over 7 configs / 70 splits (mean winner: logistic)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.33 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=40.0 (1840 rows / 46 features)
- **INFO** dof: dead-feature fraction (synthetic — informational) — dead_frac=0.89 (41 near-zero-importance features) — expected: benchmark plants signal in ~6/36
- **INFO** dof note — low/zero-importance: ['direction', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 10 live labeled trades < 30; rerun after live history accrues

7 passed, 0 failed (22s)
