# Overfit audit — 2026-09-11 18:29 UTC

Dataset: live history (17977 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.760 oof_auc=0.543 gap=+0.218; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.826 oof_auc=0.544 gap=+0.282; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.717 oof_auc=0.542 gap=+0.175; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2681 vs base-rate constant 0.2442 (base=0.424, n=14980) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2612 vs base-rate constant 0.2442 (base=0.424, n=14980) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2865 vs base-rate constant 0.2442 (base=0.424, n=14980) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.503 z=1.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.39 over 6 configs / 70 splits (mean winner: gbt_d3_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.33 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.144, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=280.9 (17977 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 17/64 features (47 of the 56 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.88 (56 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'mtf_align', 'opt_oi_pcr_z', 'corr_shift', 'pd_zone', 'opt_iv_skew'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr: P(true SR > 0) on conviction-only sample [ABSTAINED - gate unsatisfiable] — dsr=0.002 sr=-0.24 n=30 (probes excluded: 404) | NOT GRADED: at n_trials=7 the threshold is sr0=1.387x|SR|, so dsr>=0.90 is attainable for NO sample and a FAIL here would carry no information. Floors and thresholds are UNCHANGED. Repair: record per-trial SR so var_trial_sr is MEASURED rather than the SR^2 fallback; this arms itself when that lands.
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=4065 (candidate=4036 live=29) base_rate=0.386
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (29 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=3475 auc=0.557 (pooled 0.544, delta_auc=+0.012) brier=0.2574 (pooled 0.2612, delta_brier=-0.0038)
- **INFO** regime[bull_vol] — n=1804 (candidate=1790 live=14) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (14 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1778 auc=0.549 (pooled 0.544, delta_auc=+0.005) brier=0.2697 (pooled 0.2612, delta_brier=+0.0085)
- **INFO** regime[range] — n=11111 (candidate=10784 live=327) base_rate=0.299
- **INFO** regime[range] oof — oof_n=3717 auc=0.552 (pooled 0.544, delta_auc=+0.008) brier=0.2613 (pooled 0.2612, delta_brier=+0.0001)
- **INFO** regime[bear] — n=7307 (candidate=7243 live=64) base_rate=0.343
- **INFO** regime[bear] oof — oof_n=2310 auc=0.524 (pooled 0.544, delta_auc=-0.020) brier=0.2782 (pooled 0.2612, delta_brier=+0.0170)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3700 auc=0.609 (pooled 0.544, delta_auc=+0.065) brier=0.2499 (pooled 0.2612, delta_brier=-0.0113)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4494] — oof_n=3745 auc=0.632 brier=0.2402
- **INFO** lc[n=7191] — oof_n=5990 auc=0.513 brier=0.2722
- **INFO** lc[n=9887] — oof_n=8235 auc=0.490 brier=0.2716
- **INFO** lc[n=12584] — oof_n=10485 auc=0.527 brier=0.2643
- **INFO** lc[n=15280] — oof_n=12730 auc=0.600 brier=0.2435
- **INFO** lc[n=17977] — oof_n=14980 auc=0.564 brier=0.2612
- **INFO** learning curve trend — FLAT (|delta_auc=+0.009| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 24.6% (n=17977) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 24.9% (n=17977) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 24.9% (n=17977) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=17977) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=17977) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=17977) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 0 failed (117s)

Corpus: live history (17977 rows)
