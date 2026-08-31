# Overfit audit — 2026-08-30 23:52 UTC

Dataset: live history (10636 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.796 oof_auc=0.483 gap=+0.313; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.794 oof_auc=0.507 gap=+0.288; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.813 oof_auc=0.515 gap=+0.298; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3379 vs base-rate constant 0.2485 (base=0.461, n=8860) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2456 vs base-rate constant 0.2485 (base=0.461, n=8860) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3159 vs base-rate constant 0.2485 (base=0.461, n=8860) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.506 z=1.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=166.2 (10636 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=386); mixed-sample dsr=0.000 sr=-0.40; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=2008 (candidate=1996 live=12) base_rate=0.360
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (12 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1605 auc=0.676 (pooled 0.507, delta_auc=+0.169) brier=0.2280 (pooled 0.2456, delta_brier=-0.0176)
- **INFO** regime[bull_vol] — n=1377 (candidate=1367 live=10) base_rate=0.460
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1338 auc=0.581 (pooled 0.507, delta_auc=+0.074) brier=0.2393 (pooled 0.2456, delta_brier=-0.0063)
- **INFO** regime[range] — n=9086 (candidate=8779 live=307) base_rate=0.264
- **INFO** regime[range] oof — oof_n=1851 auc=0.564 (pooled 0.507, delta_auc=+0.058) brier=0.2431 (pooled 0.2456, delta_brier=-0.0025)
- **INFO** regime[bear] — n=6372 (candidate=6315 live=57) base_rate=0.320
- **INFO** regime[bear] oof — oof_n=1879 auc=0.600 (pooled 0.507, delta_auc=+0.094) brier=0.2395 (pooled 0.2456, delta_brier=-0.0060)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.528 (pooled 0.507, delta_auc=+0.022) brier=0.2696 (pooled 0.2456, delta_brier=+0.0240)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2659] — oof_n=2215 auc=0.575 brier=0.2456
- **INFO** lc[n=4254] — oof_n=3545 auc=0.628 brier=0.2351
- **INFO** lc[n=5850] — oof_n=4875 auc=0.598 brier=0.2544
- **INFO** lc[n=7445] — oof_n=6200 auc=0.496 brier=0.2645
- **INFO** lc[n=9041] — oof_n=7530 auc=0.506 brier=0.2780
- **INFO** lc[n=10636] — oof_n=8860 auc=0.609 brier=0.2456
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.044 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 39.4% (n=10636) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 39.8% (n=10636) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 39.8% (n=10636) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.9% (n=10636) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=10636) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=10636) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (49s)

Corpus: live history (10636 rows)
