# Overfit audit — 2026-07-28 22:07 UTC

Dataset: live history (866 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.836 oof_auc=0.506 gap=+0.329
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.829 oof_auc=0.539 gap=+0.290
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.843 oof_auc=0.478 gap=+0.365
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.525 z=2.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=14.0 (866 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.65 (40 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['manip_suspect', 'mtf_align', 'corr_fast', 'corr_shift', 'th_barclose', 'imbalance_delta_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=249); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4840 (candidate=4597 live=243) base_rate=0.198
- **INFO** regime[range] oof — oof_n=338 auc=0.522 (pooled 0.539, delta_auc=-0.017) brier=0.2535 (pooled 0.2437, delta_brier=+0.0098)
- **INFO** regime[bear] — n=966 (candidate=960 live=6) base_rate=0.166
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=238 auc=0.489 (pooled 0.539, delta_auc=-0.050) brier=0.2298 (pooled 0.2437, delta_brier=-0.0139)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

3 passed, 4 failed (27s)
