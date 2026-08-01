# Overfit audit — 2026-08-01 21:37 UTC

Dataset: live history (1249 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.860 oof_auc=0.531 gap=+0.328
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.877 oof_auc=0.586 gap=+0.291
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.857 oof_auc=0.557 gap=+0.300
- **INFO** null-floor[logistic] — OOF Brier 0.2425 vs base-rate constant 0.1419 (base=0.171, n=1040) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2148 vs base-rate constant 0.1419 (base=0.171, n=1040) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2518 vs base-rate constant 0.1419 (base=0.171, n=1040) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.487 z=1.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=19.5 (1249 rows / 64 features)
- **PASS** dof: dead-feature fraction under 55% (live data) — dead_frac=0.50 (32 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'va_pos', 'ret_12_dir', 'corr_shift', 'fvg_liq_confluence', 'pat_hammer_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 17 conviction-marked live trades < 30 (mixed n=277); mixed-sample dsr=0.000 sr=-0.54; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=5 (candidate=5 live=0) base_rate=0.200
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=5 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6090 (candidate=5833 live=257) base_rate=0.196
- **INFO** regime[range] oof — oof_n=480 auc=0.523 (pooled 0.586, delta_auc=-0.062) brier=0.2126 (pooled 0.2148, delta_brier=-0.0023)
- **INFO** regime[bear] — n=2265 (candidate=2245 live=20) base_rate=0.189
- **INFO** regime[bear] FLAG — insufficient live coverage (20 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=555 auc=0.512 (pooled 0.586, delta_auc=-0.074) brier=0.2170 (pooled 0.2148, delta_brier=+0.0022)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=312] — oof_n=104 auc=0.586 brier=0.1949
- **INFO** lc[n=500] — oof_n=249 auc=0.479 brier=0.2501
- **INFO** lc[n=687] — oof_n=456 auc=0.518 brier=0.2569
- **INFO** lc[n=874] — oof_n=580 auc=0.519 brier=0.2257
- **INFO** lc[n=1062] — oof_n=708 auc=0.613 brier=0.2084
- **INFO** lc[n=1249] — oof_n=1040 auc=0.518 brier=0.2148
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.033 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=1249) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=1249) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=1249) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 3.8% (n=1249) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1249) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1249) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 3 failed (44s)
