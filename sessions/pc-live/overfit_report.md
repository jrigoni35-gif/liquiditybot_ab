# Overfit audit — 2026-09-05 12:39 UTC

Dataset: live history (14634 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.786 oof_auc=0.542 gap=+0.244; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.812 oof_auc=0.526 gap=+0.286; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.814 oof_auc=0.551 gap=+0.263; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2851 vs base-rate constant 0.2440 (base=0.423, n=10974) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2773 vs base-rate constant 0.2440 (base=0.423, n=10974) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3109 vs base-rate constant 0.2440 (base=0.423, n=10974) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=228.7 (14634 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 19/64 features (45 of the 52 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.81 (52 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['equity_risk_z', 'dominance_delta', 'basis_dir', 'hour_cos', 'ret_1_dir', 'ret_6_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=409); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=2949 (candidate=2931 live=18) base_rate=0.386
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (18 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=2365 auc=0.523 (pooled 0.526, delta_auc=-0.003) brier=0.2702 (pooled 0.2773, delta_brier=-0.0071)
- **INFO** regime[bull_vol] — n=1686 (candidate=1673 live=13) base_rate=0.460
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1644 auc=0.568 (pooled 0.526, delta_auc=+0.042) brier=0.2766 (pooled 0.2773, delta_brier=-0.0006)
- **INFO** regime[range] — n=10324 (candidate=10008 live=316) base_rate=0.296
- **INFO** regime[range] oof — oof_n=2919 auc=0.535 (pooled 0.526, delta_auc=+0.009) brier=0.2639 (pooled 0.2773, delta_brier=-0.0134)
- **INFO** regime[bear] — n=6922 (candidate=6860 live=62) base_rate=0.331
- **INFO** regime[bear] oof — oof_n=1900 auc=0.493 (pooled 0.526, delta_auc=-0.033) brier=0.3024 (pooled 0.2773, delta_brier=+0.0251)
- **INFO** regime[crisis] — n=3151 (candidate=3151 live=0) base_rate=0.472
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2146 auc=0.538 (pooled 0.526, delta_auc=+0.013) brier=0.2815 (pooled 0.2773, delta_brier=+0.0043)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=3658] — oof_n=3045 auc=0.616 brier=0.2292
- **INFO** lc[n=5854] — oof_n=4875 auc=0.598 brier=0.2544
- **INFO** lc[n=8049] — oof_n=6705 auc=0.608 brier=0.2531
- **INFO** lc[n=10244] — oof_n=8535 auc=0.511 brier=0.2646
- **INFO** lc[n=12439] — oof_n=10365 auc=0.507 brier=0.2748
- **INFO** lc[n=14634] — oof_n=12195 auc=0.570 brier=0.2466
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.069 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 30.2% (n=14634) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 30.6% (n=14634) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 30.6% (n=14634) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.4% (n=14634) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=14634) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=14634) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (71s)

Corpus: live history (14634 rows)
