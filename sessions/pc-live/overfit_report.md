# Overfit audit — 2026-08-29 21:24 UTC

Dataset: live history (8998 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.809 oof_auc=0.493 gap=+0.316; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.855 oof_auc=0.504 gap=+0.351; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.807 oof_auc=0.507 gap=+0.301; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3334 vs base-rate constant 0.2500 (base=0.496, n=7495) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2861 vs base-rate constant 0.2500 (base=0.496, n=7495) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3366 vs base-rate constant 0.2500 (base=0.496, n=7495) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.503 z=0.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=140.6 (8998 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.95 (61 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'vol_percentile', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=376); mixed-sample dsr=0.000 sr=-0.39; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1348 (candidate=1338 live=10) base_rate=0.375
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1000 auc=0.393 (pooled 0.504, delta_auc=-0.111) brier=0.2940 (pooled 0.2861, delta_brier=+0.0079)
- **INFO** regime[bull_vol] — n=1187 (candidate=1178 live=9) base_rate=0.459
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1165 auc=0.568 (pooled 0.504, delta_auc=+0.064) brier=0.2802 (pooled 0.2861, delta_brier=-0.0060)
- **INFO** regime[range] — n=8557 (candidate=8257 live=300) base_rate=0.259
- **INFO** regime[range] oof — oof_n=1439 auc=0.418 (pooled 0.504, delta_auc=-0.086) brier=0.3000 (pooled 0.2861, delta_brier=+0.0139)
- **INFO** regime[bear] — n=6079 (candidate=6022 live=57) base_rate=0.328
- **INFO** regime[bear] oof — oof_n=1704 auc=0.408 (pooled 0.504, delta_auc=-0.096) brier=0.3125 (pooled 0.2861, delta_brier=+0.0263)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.572 (pooled 0.504, delta_auc=+0.068) brier=0.2561 (pooled 0.2861, delta_brier=-0.0301)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2250] — oof_n=1875 auc=0.536 brier=0.2644
- **INFO** lc[n=3599] — oof_n=2995 auc=0.609 brier=0.2484
- **INFO** lc[n=4949] — oof_n=4120 auc=0.566 brier=0.2687
- **INFO** lc[n=6299] — oof_n=5245 auc=0.574 brier=0.2514
- **INFO** lc[n=7648] — oof_n=6370 auc=0.565 brier=0.2590
- **INFO** lc[n=8998] — oof_n=7495 auc=0.502 brier=0.2861
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.039 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 28.9% (n=8998) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 29.3% (n=8998) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 29.3% (n=8998) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.2% (n=8998) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=8998) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=8998) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (50s)

Corpus: live history (8998 rows)
