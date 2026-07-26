# Overfit audit — 2026-07-26 16:29 UTC

Dataset: live history (4715 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.726 oof_auc=0.515 gap=+0.211
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.763 oof_auc=0.551 gap=+0.212
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.750 oof_auc=0.502 gap=+0.248
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.519 z=2.9 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.03 over 7 configs / 70 splits (mean winner: gbt_d3_lr10)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.01 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=76.0 (4715 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.61 (38 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['pd_zone', 'ret_12_dir', 'regime_age', 'imbalance_dir', 'vol_term', 'th_stopzone'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=240); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4261 (candidate=4025 live=236) base_rate=0.185
- **INFO** regime[range] oof — oof_n=3413 auc=0.631 (pooled 0.551, delta_auc=+0.079) brier=0.2225 (pooled 0.2143, delta_brier=+0.0082)
- **INFO** regime[bear] — n=534 (candidate=530 live=4) base_rate=0.079
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=512 auc=0.680 (pooled 0.551, delta_auc=+0.128) brier=0.1595 (pooled 0.2143, delta_brier=-0.0548)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

4 passed, 4 failed (131s)
