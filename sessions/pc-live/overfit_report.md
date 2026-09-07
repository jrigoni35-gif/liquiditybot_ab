# Overfit audit — 2026-09-07 14:28 UTC

Dataset: live history (16400 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.769 oof_auc=0.550 gap=+0.219; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.821 oof_auc=0.553 gap=+0.268; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.762 oof_auc=0.545 gap=+0.217; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2750 vs base-rate constant 0.2472 (base=0.447, n=13665) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2485 vs base-rate constant 0.2472 (base=0.447, n=13665) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3075 vs base-rate constant 0.2472 (base=0.447, n=13665) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.499 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=256.2 (16400 rows / 64 features)
- **INFO** dof coverage — fitted GBT consulted 46/64 features - dead read taken on a model that actually looked
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.78 (50 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['vol_percentile', 'sigma_bar_pct', 'equity_risk_z', 'th_barclose', 'poc_dist', 'mkt_ret_6_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=414); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3381 (candidate=3360 live=21) base_rate=0.409
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (21 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=2801 auc=0.584 (pooled 0.553, delta_auc=+0.031) brier=0.2510 (pooled 0.2485, delta_brier=+0.0025)
- **INFO** regime[bull_vol] — n=1736 (candidate=1723 live=13) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1711 auc=0.569 (pooled 0.553, delta_auc=+0.016) brier=0.2481 (pooled 0.2485, delta_brier=-0.0004)
- **INFO** regime[range] — n=10608 (candidate=10291 live=317) base_rate=0.301
- **INFO** regime[range] oof — oof_n=3227 auc=0.610 (pooled 0.553, delta_auc=+0.057) brier=0.2422 (pooled 0.2485, delta_brier=-0.0063)
- **INFO** regime[bear] — n=7214 (candidate=7151 live=63) base_rate=0.340
- **INFO** regime[bear] oof — oof_n=2217 auc=0.551 (pooled 0.553, delta_auc=-0.002) brier=0.2623 (pooled 0.2485, delta_brier=+0.0138)
- **INFO** regime[crisis] — n=3866 (candidate=3866 live=0) base_rate=0.459
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3709 auc=0.632 (pooled 0.553, delta_auc=+0.079) brier=0.2441 (pooled 0.2485, delta_brier=-0.0044)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4100] — oof_n=3415 auc=0.639 brier=0.2264
- **INFO** lc[n=6560] — oof_n=5465 auc=0.586 brier=0.2493
- **INFO** lc[n=9020] — oof_n=7515 auc=0.508 brier=0.2759
- **INFO** lc[n=11480] — oof_n=9565 auc=0.504 brier=0.2648
- **INFO** lc[n=13940] — oof_n=11615 auc=0.564 brier=0.2610
- **INFO** lc[n=16400] — oof_n=13665 auc=0.596 brier=0.2485
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.032 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 27.0% (n=16400) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 27.3% (n=16400) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 27.3% (n=16400) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=16400) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=16400) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=16400) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (103s)

Corpus: live history (16400 rows)
