# Overfit audit — 2026-08-09 04:30 UTC

Dataset: live history (9739 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.705 oof_auc=0.514 gap=+0.191
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.732 oof_auc=0.545 gap=+0.188
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.774 oof_auc=0.508 gap=+0.266
- **INFO** null-floor[logistic] — OOF Brier 0.2876 vs base-rate constant 0.1551 (base=0.192, n=8115) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2064 vs base-rate constant 0.1551 (base=0.192, n=8115) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3902 vs base-rate constant 0.1551 (base=0.192, n=8115) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.13 over 8 configs / 70 splits (mean winner: gbt_d2_lr10)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.29 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.191, combos_dropped=0
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=152.2 (9739 rows / 64 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.97 (62 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 19 conviction-marked live trades < 30 (mixed n=305); mixed-sample dsr=0.000 sr=-0.49; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=36 (candidate=34 live=2) base_rate=0.306
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=36 auc=0.511 (pooled 0.545, delta_auc=-0.034) brier=0.2344 (pooled 0.2064, delta_brier=+0.0280)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=8 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6488 (candidate=6221 live=267) base_rate=0.202
- **INFO** regime[range] oof — oof_n=4798 auc=0.528 (pooled 0.545, delta_auc=-0.017) brier=0.2078 (pooled 0.2064, delta_brier=+0.0015)
- **INFO** regime[bear] — n=3333 (candidate=3297 live=36) base_rate=0.215
- **INFO** regime[bear] oof — oof_n=3273 auc=0.564 (pooled 0.545, delta_auc=+0.019) brier=0.2039 (pooled 0.2064, delta_brier=-0.0025)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2435] — oof_n=2025 auc=0.519 brier=0.2616
- **INFO** lc[n=3896] — oof_n=3245 auc=0.609 brier=0.2321
- **INFO** lc[n=5356] — oof_n=4460 auc=0.559 brier=0.2129
- **INFO** lc[n=6817] — oof_n=5680 auc=0.546 brier=0.2041
- **INFO** lc[n=8278] — oof_n=6895 auc=0.540 brier=0.2001
- **INFO** lc[n=9739] — oof_n=8115 auc=0.542 brier=0.2064
- **INFO** learning curve trend — FLAT (|delta_auc=-0.023| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 94.1% (n=9739)
- **INFO** extras[opt_pcr_z] — at-neutral share 94.9% (n=9739)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 97.4% (n=9739) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 12.8% (n=9739) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=9739) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=9739) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 4 failed (244s)
