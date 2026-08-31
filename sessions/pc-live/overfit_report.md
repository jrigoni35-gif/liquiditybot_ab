# Overfit audit — 2026-08-31 01:09 UTC

Dataset: live history (10675 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.796 oof_auc=0.480 gap=+0.316; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.832 oof_auc=0.486 gap=+0.346; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.826 oof_auc=0.503 gap=+0.323; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3377 vs base-rate constant 0.2484 (base=0.460, n=8895) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2677 vs base-rate constant 0.2484 (base=0.460, n=8895) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3198 vs base-rate constant 0.2484 (base=0.460, n=8895) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.496 z=1.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=166.8 (10675 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.98 (63 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 27 conviction-marked live trades < 30 (mixed n=387); mixed-sample dsr=0.000 sr=-0.40; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=2018 (candidate=2006 live=12) base_rate=0.359
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (12 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1615 auc=0.552 (pooled 0.486, delta_auc=+0.065) brier=0.2502 (pooled 0.2677, delta_brier=-0.0175)
- **INFO** regime[bull_vol] — n=1379 (candidate=1368 live=11) base_rate=0.460
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (11 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1355 auc=0.569 (pooled 0.486, delta_auc=+0.083) brier=0.2428 (pooled 0.2677, delta_brier=-0.0249)
- **INFO** regime[range] — n=9090 (candidate=8783 live=307) base_rate=0.264
- **INFO** regime[range] oof — oof_n=1861 auc=0.527 (pooled 0.486, delta_auc=+0.041) brier=0.2541 (pooled 0.2677, delta_brier=-0.0136)
- **INFO** regime[bear] — n=6373 (candidate=6316 live=57) base_rate=0.320
- **INFO** regime[bear] oof — oof_n=1877 auc=0.466 (pooled 0.486, delta_auc=-0.020) brier=0.2708 (pooled 0.2677, delta_brier=+0.0031)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.510 (pooled 0.486, delta_auc=+0.024) brier=0.3049 (pooled 0.2677, delta_brier=+0.0373)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2669] — oof_n=2220 auc=0.521 brier=0.2607
- **INFO** lc[n=4270] — oof_n=3555 auc=0.677 brier=0.2187
- **INFO** lc[n=5871] — oof_n=4890 auc=0.564 brier=0.2605
- **INFO** lc[n=7472] — oof_n=6225 auc=0.640 brier=0.2494
- **INFO** lc[n=9074] — oof_n=7560 auc=0.509 brier=0.2807
- **INFO** lc[n=10675] — oof_n=8895 auc=0.512 brier=0.2677
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.088 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 39.6% (n=10675) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 40.0% (n=10675) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 40.0% (n=10675) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.9% (n=10675) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=10675) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=10675) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (63s)

Corpus: live history (10675 rows)
