# Overfit audit — 2026-09-01 22:56 UTC

Dataset: live history (12066 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.785 oof_auc=0.504 gap=+0.281; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.798 oof_auc=0.496 gap=+0.302; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.767 oof_auc=0.504 gap=+0.264; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3320 vs base-rate constant 0.2477 (base=0.452, n=10055) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2758 vs base-rate constant 0.2477 (base=0.452, n=10055) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3095 vs base-rate constant 0.2477 (base=0.452, n=10055) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=188.5 (12066 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 22/64 features (42 of the 57 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.89 (57 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'liq_pocket_pull', 'va_pos', 'poc_dist', 'corr_fast', 'corr_shift'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 27 conviction-marked live trades < 30 (mixed n=391); mixed-sample dsr=0.000 sr=-0.40; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=2339 (candidate=2326 live=13) base_rate=0.378
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1882 auc=0.493 (pooled 0.496, delta_auc=-0.003) brier=0.2561 (pooled 0.2758, delta_brier=-0.0198)
- **INFO** regime[bull_vol] — n=1454 (candidate=1443 live=11) base_rate=0.450
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (11 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1431 auc=0.563 (pooled 0.496, delta_auc=+0.068) brier=0.2622 (pooled 0.2758, delta_brier=-0.0137)
- **INFO** regime[range] — n=9526 (candidate=9216 live=310) base_rate=0.274
- **INFO** regime[range] oof — oof_n=2249 auc=0.454 (pooled 0.496, delta_auc=-0.042) brier=0.2685 (pooled 0.2758, delta_brier=-0.0074)
- **INFO** regime[bear] — n=6478 (candidate=6421 live=57) base_rate=0.323
- **INFO** regime[bear] oof — oof_n=1848 auc=0.443 (pooled 0.496, delta_auc=-0.053) brier=0.2920 (pooled 0.2758, delta_brier=+0.0162)
- **INFO** regime[crisis] — n=2645 (candidate=2645 live=0) base_rate=0.484
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2645 auc=0.483 (pooled 0.496, delta_auc=-0.013) brier=0.2923 (pooled 0.2758, delta_brier=+0.0164)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=3016] — oof_n=2510 auc=0.576 brier=0.2477
- **INFO** lc[n=4826] — oof_n=4020 auc=0.588 brier=0.2563
- **INFO** lc[n=6636] — oof_n=5530 auc=0.577 brier=0.2531
- **INFO** lc[n=8446] — oof_n=7035 auc=0.555 brier=0.2554
- **INFO** lc[n=10256] — oof_n=8545 auc=0.513 brier=0.2658
- **INFO** lc[n=12066] — oof_n=10055 auc=0.483 brier=0.2758
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.084 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 36.7% (n=12066) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 37.0% (n=12066) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 37.0% (n=12066) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.7% (n=12066) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=12066) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=12066) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (80s)

Corpus: live history (12066 rows)
