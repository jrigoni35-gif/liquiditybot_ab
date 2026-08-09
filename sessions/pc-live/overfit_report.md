# Overfit audit — 2026-08-09 05:50 UTC

Dataset: live history (692 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.881 oof_auc=0.459 gap=+0.422
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.869 oof_auc=0.452 gap=+0.416
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.933 oof_auc=0.425 gap=+0.507
- **INFO** null-floor[logistic] — OOF Brier 0.4061 vs base-rate constant 0.2432 (base=0.417, n=460) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2941 vs base-rate constant 0.2432 (base=0.417, n=460) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4607 vs base-rate constant 0.2432 (base=0.417, n=460) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.498 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=10.8 (692 rows / 64 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.95 (61 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 19 conviction-marked live trades < 30 (mixed n=305); mixed-sample dsr=0.000 sr=-0.49; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=42 (candidate=40 live=2) base_rate=0.262
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=41 auc=0.534 (pooled 0.452, delta_auc=+0.082) brier=0.2260 (pooled 0.2941, delta_brier=-0.0681)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6492 (candidate=6225 live=267) base_rate=0.202
- **INFO** regime[range] oof — oof_n=88 auc=0.576 (pooled 0.452, delta_auc=+0.123) brier=0.2568 (pooled 0.2941, delta_brier=-0.0373)
- **INFO** regime[bear] — n=3337 (candidate=3301 live=36) base_rate=0.215
- **INFO** regime[bear] oof — oof_n=330 auc=0.400 (pooled 0.452, delta_auc=-0.052) brier=0.3127 (pooled 0.2941, delta_brier=+0.0186)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=173] — oof_n=0 < 40 — not scored
- **INFO** lc[n=277] — oof_n=46 auc=0.340 brier=0.3814
- **INFO** lc[n=381] — oof_n=126 auc=0.359 brier=0.3248
- **INFO** lc[n=484] — oof_n=240 auc=0.423 brier=0.3370
- **INFO** lc[n=588] — oof_n=294 auc=0.465 brier=0.3038
- **INFO** lc[n=692] — oof_n=460 auc=0.448 brier=0.2941
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.106 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 89.0% (n=692)
- **INFO** extras[opt_pcr_z] — at-neutral share 90.0% (n=692)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 99.7% (n=692) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 3.9% (n=692) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=692) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=692) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (37s)
