# Overfit audit — 2026-08-29 21:58 UTC

Dataset: live history (9006 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.808 oof_auc=0.495 gap=+0.314; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.852 oof_auc=0.498 gap=+0.354; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.806 oof_auc=0.499 gap=+0.307; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3325 vs base-rate constant 0.2500 (base=0.496, n=7505) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2778 vs base-rate constant 0.2500 (base=0.496, n=7505) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3402 vs base-rate constant 0.2500 (base=0.496, n=7505) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.496 z=1.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=140.7 (9006 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['opt_pcr_z', 'ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=377); mixed-sample dsr=0.000 sr=-0.39; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1353 (candidate=1342 live=11) base_rate=0.376
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (11 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1003 auc=0.390 (pooled 0.498, delta_auc=-0.108) brier=0.2874 (pooled 0.2778, delta_brier=+0.0096)
- **INFO** regime[bull_vol] — n=1187 (candidate=1178 live=9) base_rate=0.459
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1165 auc=0.581 (pooled 0.498, delta_auc=+0.082) brier=0.2633 (pooled 0.2778, delta_brier=-0.0145)
- **INFO** regime[range] — n=8557 (candidate=8257 live=300) base_rate=0.259
- **INFO** regime[range] oof — oof_n=1439 auc=0.423 (pooled 0.498, delta_auc=-0.075) brier=0.2871 (pooled 0.2778, delta_brier=+0.0093)
- **INFO** regime[bear] — n=6083 (candidate=6026 live=57) base_rate=0.328
- **INFO** regime[bear] oof — oof_n=1711 auc=0.410 (pooled 0.498, delta_auc=-0.088) brier=0.3039 (pooled 0.2778, delta_brier=+0.0261)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.552 (pooled 0.498, delta_auc=+0.054) brier=0.2546 (pooled 0.2778, delta_brier=-0.0232)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2252] — oof_n=1875 auc=0.536 brier=0.2644
- **INFO** lc[n=3602] — oof_n=3000 auc=0.619 brier=0.2370
- **INFO** lc[n=4953] — oof_n=4125 auc=0.559 brier=0.2705
- **INFO** lc[n=6304] — oof_n=5250 auc=0.575 brier=0.2514
- **INFO** lc[n=7655] — oof_n=6375 auc=0.569 brier=0.2587
- **INFO** lc[n=9006] — oof_n=7505 auc=0.510 brier=0.2778
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.038 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 28.9% (n=9006) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 29.3% (n=9006) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 29.3% (n=9006) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.2% (n=9006) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=9006) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=9006) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (48s)

Corpus: live history (9006 rows)
