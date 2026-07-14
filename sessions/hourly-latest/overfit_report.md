# Overfit audit — 2026-07-13 23:20 UTC

Dataset: SYNTHETIC benchmark (live rows=0 < 570) — validating machinery, not market

- **PASS** gap[logistic]: OOF gap within memorization band — train_auc=0.659 oof_auc=0.638 gap=+0.021
- **PASS** gap[gbt]: OOF gap within memorization band — train_auc=0.713 oof_auc=0.627 gap=+0.087
- **PASS** gap[mlp]: OOF gap within memorization band — train_auc=0.680 oof_auc=0.642 gap=+0.038
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.503 z=0.4 (limit 3.0)
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.13 over 7 configs / 70 splits (mean winner: logistic)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.13 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=40.0 (2280 rows / 57 features)
- **INFO** dof: dead-feature fraction (synthetic — informational) — dead_frac=0.91 (52 near-zero-importance features) — expected: benchmark plants signal in ~6/36
- **INFO** dof note — low/zero-importance: ['ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile', 'spread_bps', 'depth_log'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 10 live labeled trades < 30; rerun after live history accrues

7 passed, 0 failed (38s)
