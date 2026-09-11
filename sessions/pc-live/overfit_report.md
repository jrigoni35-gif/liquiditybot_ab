# Overfit audit — 2026-09-10 23:44 UTC

Dataset: live history (17570 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.760 oof_auc=0.543 gap=+0.217; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.798 oof_auc=0.551 gap=+0.247; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.726 oof_auc=0.537 gap=+0.190; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2666 vs base-rate constant 0.2443 (base=0.425, n=14640) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2438 vs base-rate constant 0.2443 (base=0.425, n=14640) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.2993 vs base-rate constant 0.2443 (base=0.425, n=14640) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.497 z=1.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.50 over 6 configs / 70 splits (mean winner: gbt_d2_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.69 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.138, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=274.5 (17570 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 23/64 features (41 of the 54 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.84 (54 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['va_pos', 'poc_dist', 'direction', 'ret_1_dir', 'ret_6_dir', 'ret_12_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=425); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3900 (candidate=3874 live=26) base_rate=0.381
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (26 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=3314 auc=0.570 (pooled 0.551, delta_auc=+0.020) brier=0.2529 (pooled 0.2438, delta_brier=+0.0090)
- **INFO** regime[bull_vol] — n=1788 (candidate=1775 live=13) base_rate=0.452
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1762 auc=0.640 (pooled 0.551, delta_auc=+0.089) brier=0.2327 (pooled 0.2438, delta_brier=-0.0112)
- **INFO** regime[range] — n=10908 (candidate=10585 live=323) base_rate=0.298
- **INFO** regime[range] oof — oof_n=3519 auc=0.610 (pooled 0.551, delta_auc=+0.059) brier=0.2393 (pooled 0.2438, delta_brier=-0.0046)
- **INFO** regime[bear] — n=7272 (candidate=7209 live=63) base_rate=0.341
- **INFO** regime[bear] oof — oof_n=2277 auc=0.568 (pooled 0.551, delta_auc=+0.017) brier=0.2537 (pooled 0.2438, delta_brier=+0.0098)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3768 auc=0.624 (pooled 0.551, delta_auc=+0.073) brier=0.2395 (pooled 0.2438, delta_brier=-0.0044)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4392] — oof_n=3660 auc=0.635 brier=0.2347
- **INFO** lc[n=7028] — oof_n=5855 auc=0.533 brier=0.2579
- **INFO** lc[n=9664] — oof_n=8050 auc=0.533 brier=0.2651
- **INFO** lc[n=12299] — oof_n=10245 auc=0.497 brier=0.2723
- **INFO** lc[n=14934] — oof_n=12445 auc=0.600 brier=0.2456
- **INFO** lc[n=17570] — oof_n=14640 auc=0.608 brier=0.2438
- **INFO** learning curve trend — FLAT (|delta_auc=+0.020| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 25.2% (n=17570) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 25.5% (n=17570) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 25.5% (n=17570) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=17570) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=17570) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=17570) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 0 failed (112s)

Corpus: live history (17570 rows)
