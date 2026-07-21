# Overfit audit — 2026-07-21 19:38 UTC

Dataset: live history (2279 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.775 oof_auc=0.457 gap=+0.318
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.746 oof_auc=0.421 gap=+0.326
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.724 oof_auc=0.455 gap=+0.269
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.483 z=2.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **FAIL** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.67 over 6 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.69 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=36.8 (2279 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.76 (47 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['pd_zone', 'pat_marubozu_dir', 'volume_z', 'mom_dir', 'fear_greed', 'fv_edge_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=96); mixed-sample dsr=0.000 sr=-0.66; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue

3 passed, 5 failed (53s)
