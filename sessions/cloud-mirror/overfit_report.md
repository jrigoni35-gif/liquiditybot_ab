# Overfit audit — 2026-07-26 05:18 UTC

Dataset: live history (4612 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.725 oof_auc=0.541 gap=+0.184
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.768 oof_auc=0.546 gap=+0.223
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.834 oof_auc=0.528 gap=+0.306
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.499 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.07 over 7 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.03 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=74.4 (4612 rows / 62 features)
- **PASS** dof: dead-feature fraction under 55% (live data) — dead_frac=0.52 (32 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'gate_confidence', 'th_stopzone', 'th_barclose', 'volume_z', 'regime_age'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=240); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4190 (candidate=3954 live=236) base_rate=0.188
- **INFO** regime[range] oof — oof_n=3359 auc=0.620 (pooled 0.546, delta_auc=+0.075) brier=0.2215 (pooled 0.2121, delta_brier=+0.0094)
- **INFO** regime[bear] — n=502 (candidate=498 live=4) base_rate=0.082
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=481 auc=0.740 (pooled 0.546, delta_auc=+0.194) brier=0.1464 (pooled 0.2121, delta_brier=-0.0657)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

5 passed, 3 failed (82s)
