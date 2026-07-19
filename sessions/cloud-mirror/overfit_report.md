# Overfit audit — 2026-07-19 23:08 UTC

Dataset: live history (1741 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.872 oof_auc=0.430 gap=+0.442
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.843 oof_auc=0.495 gap=+0.348
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.809 oof_auc=0.451 gap=+0.358
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.494 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=30.0 (1741 rows / 58 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.97 (56 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — INFORMATIONAL during exploration phase — dsr=0.000 sr=-0.69 n=45; live sample is EV-mixed by design (PT-050 probes); gate arms when ml.exploration.enabled is false

3 passed, 4 failed (16s)
