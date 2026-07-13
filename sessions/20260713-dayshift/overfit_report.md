# Overfit audit — 2026-07-13 13:36 UTC

Dataset: SYNTHETIC benchmark (live rows=4 < 430) — validating machinery, not market

- **PASS** gap[logistic]: OOF gap within memorization band — train_auc=0.636 oof_auc=0.616 gap=+0.020
- **PASS** gap[gbt]: OOF gap within memorization band — train_auc=0.695 oof_auc=0.605 gap=+0.090
- **PASS** gap[mlp]: OOF gap within memorization band — train_auc=0.683 oof_auc=0.627 gap=+0.056
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.483 z=2.0 (limit 3.0)
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.17 over 7 configs / 70 splits (mean winner: logistic)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.30 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=35.0 (1505 rows / 43 features)
- **INFO** dof: dead-feature fraction (synthetic — informational) — dead_frac=0.91 (39 near-zero-importance features) — expected: benchmark plants signal in ~6/36
- **INFO** dof note — low/zero-importance: ['volume_z', 'direction', 'ret_12', 'ret_48', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 live labeled trades < 30; rerun after live history accrues

7 passed, 0 failed (22s)
