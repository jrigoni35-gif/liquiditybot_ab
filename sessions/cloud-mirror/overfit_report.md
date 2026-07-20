# Overfit audit — 2026-07-20 11:29 UTC

Dataset: live history (1934 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.781 oof_auc=0.539 gap=+0.242
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.750 oof_auc=0.402 gap=+0.348
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.686 oof_auc=0.443 gap=+0.243
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.493 z=0.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=33.3 (1934 rows / 58 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.78 (45 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['funding_dist', 'ret_1_dir', 'ret_48_dir', 'imbalance_dir', 'basis_dir', 'volume_z'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 0 conviction-marked live trades < 30 (mixed n=57); mixed-sample dsr=0.000 sr=-0.65; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue

3 passed, 4 failed (20s)
