# Overfit audit — 2026-09-03 05:10 UTC

Dataset: live history (13042 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.780 oof_auc=0.527 gap=+0.253; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.816 oof_auc=0.556 gap=+0.260; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.759 oof_auc=0.504 gap=+0.255; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3276 vs base-rate constant 0.2480 (base=0.455, n=10865) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2500 vs base-rate constant 0.2480 (base=0.455, n=10865) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3113 vs base-rate constant 0.2480 (base=0.455, n=10865) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=203.8 (13042 rows / 64 features)
- **INFO** dof coverage — fitted GBT consulted 50/64 features - dead read taken on a model that actually looked
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.78 (50 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['regime_crisis', 'sigma_bar_pct', 'manip_suspect', 'mkt_ret_6_dir', 'corr_fast', 'va_pos'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at /home/user/liquiditybot_ab/outputs/trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 27 conviction-marked live trades < 30 (mixed n=399); mixed-sample dsr=0.000 sr=-0.41; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=2431 (candidate=2417 live=14) base_rate=0.382
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (14 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1948 auc=0.616 (pooled 0.556, delta_auc=+0.060) brier=0.2403 (pooled 0.2500, delta_brier=-0.0097)
- **INFO** regime[bull_vol] — n=1559 (candidate=1547 live=12) base_rate=0.459
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (12 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1531 auc=0.630 (pooled 0.556, delta_auc=+0.074) brier=0.2379 (pooled 0.2500, delta_brier=-0.0121)
- **INFO** regime[range] — n=9921 (candidate=9606 live=315) base_rate=0.284
- **INFO** regime[range] oof — oof_n=2575 auc=0.579 (pooled 0.556, delta_auc=+0.023) brier=0.2494 (pooled 0.2500, delta_brier=-0.0006)
- **INFO** regime[bear] — n=6563 (candidate=6505 live=58) base_rate=0.327
- **INFO** regime[bear] oof — oof_n=1858 auc=0.597 (pooled 0.556, delta_auc=+0.041) brier=0.2501 (pooled 0.2500, delta_brier=+0.0002)
- **INFO** regime[crisis] — n=2955 (candidate=2955 live=0) base_rate=0.482
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2953 auc=0.541 (pooled 0.556, delta_auc=-0.015) brier=0.2631 (pooled 0.2500, delta_brier=+0.0131)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=3260] — oof_n=2715 auc=0.673 brier=0.2274
- **INFO** lc[n=5217] — oof_n=4345 auc=0.620 brier=0.2440
- **INFO** lc[n=7173] — oof_n=5975 auc=0.502 brier=0.2773
- **INFO** lc[n=9129] — oof_n=7605 auc=0.544 brier=0.2593
- **INFO** lc[n=11086] — oof_n=9235 auc=0.524 brier=0.2600
- **INFO** lc[n=13042] — oof_n=10865 auc=0.587 brier=0.2500
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.091 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 33.9% (n=13042) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 34.3% (n=13042) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 34.3% (n=13042) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.5% (n=13042) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=13042) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=13042) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (68s)

Corpus: live history (13042 rows)
