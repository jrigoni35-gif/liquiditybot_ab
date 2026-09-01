# Overfit audit — 2026-09-01 01:32 UTC

Dataset: live history (11159 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.789 oof_auc=0.479 gap=+0.310; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.790 oof_auc=0.530 gap=+0.260; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.819 oof_auc=0.515 gap=+0.304; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3386 vs base-rate constant 0.2485 (base=0.461, n=9295) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2565 vs base-rate constant 0.2485 (base=0.461, n=9295) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3145 vs base-rate constant 0.2485 (base=0.461, n=9295) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=174.4 (11159 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 2/64 features (62 of the 62 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 27 conviction-marked live trades < 30 (mixed n=389); mixed-sample dsr=0.000 sr=-0.40; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=2195 (candidate=2183 live=12) base_rate=0.385
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (12 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1776 auc=0.642 (pooled 0.530, delta_auc=+0.112) brier=0.2360 (pooled 0.2565, delta_brier=-0.0205)
- **INFO** regime[bull_vol] — n=1423 (candidate=1412 live=11) base_rate=0.453
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (11 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1400 auc=0.600 (pooled 0.530, delta_auc=+0.070) brier=0.2392 (pooled 0.2565, delta_brier=-0.0173)
- **INFO** regime[range] — n=9313 (candidate=9004 live=309) base_rate=0.268
- **INFO** regime[range] oof — oof_n=2056 auc=0.545 (pooled 0.530, delta_auc=+0.015) brier=0.2505 (pooled 0.2565, delta_brier=-0.0059)
- **INFO** regime[bear] — n=6414 (candidate=6357 live=57) base_rate=0.322
- **INFO** regime[bear] oof — oof_n=1876 auc=0.459 (pooled 0.530, delta_auc=-0.071) brier=0.2651 (pooled 0.2565, delta_brier=+0.0087)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.508 (pooled 0.530, delta_auc=-0.022) brier=0.2823 (pooled 0.2565, delta_brier=+0.0258)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2790] — oof_n=2325 auc=0.501 brier=0.2554
- **INFO** lc[n=4464] — oof_n=3720 auc=0.655 brier=0.2325
- **INFO** lc[n=6137] — oof_n=5110 auc=0.575 brier=0.2591
- **INFO** lc[n=7811] — oof_n=6505 auc=0.604 brier=0.2537
- **INFO** lc[n=9485] — oof_n=7900 auc=0.539 brier=0.2555
- **INFO** lc[n=11159] — oof_n=9295 auc=0.555 brier=0.2565
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.031 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 39.3% (n=11159) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 39.6% (n=11159) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 39.6% (n=11159) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.8% (n=11159) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=11159) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=11159) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (51s)

Corpus: live history (11159 rows)
