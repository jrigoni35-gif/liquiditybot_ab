# Overfit audit — 2026-09-11 02:49 UTC

Dataset: live history (17586 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.760 oof_auc=0.543 gap=+0.218; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.800 oof_auc=0.551 gap=+0.249; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.756 oof_auc=0.544 gap=+0.213; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2667 vs base-rate constant 0.2443 (base=0.425, n=14655) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2442 vs base-rate constant 0.2443 (base=0.425, n=14655) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3054 vs base-rate constant 0.2443 (base=0.425, n=14655) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.29 over 6 configs / 70 splits (mean winner: gbt_d2_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.66 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.138, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=274.8 (17586 rows / 64 features)
- **INFO** dof coverage — fitted GBT consulted 38/64 features - dead read taken on a model that actually looked
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.81 (52 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['corr_shift', 'poc_dist', 'drawdown_pct', 'fv_edge_bps', 'mkt_ret_6_dir', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=426); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3902 (candidate=3876 live=26) base_rate=0.381
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (26 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=3317 auc=0.579 (pooled 0.551, delta_auc=+0.028) brier=0.2522 (pooled 0.2442, delta_brier=+0.0080)
- **INFO** regime[bull_vol] — n=1800 (candidate=1786 live=14) base_rate=0.453
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (14 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1774 auc=0.637 (pooled 0.551, delta_auc=+0.086) brier=0.2327 (pooled 0.2442, delta_brier=-0.0115)
- **INFO** regime[range] — n=10911 (candidate=10588 live=323) base_rate=0.298
- **INFO** regime[range] oof — oof_n=3522 auc=0.612 (pooled 0.551, delta_auc=+0.061) brier=0.2398 (pooled 0.2442, delta_brier=-0.0044)
- **INFO** regime[bear] — n=7272 (candidate=7209 live=63) base_rate=0.341
- **INFO** regime[bear] oof — oof_n=2277 auc=0.580 (pooled 0.551, delta_auc=+0.029) brier=0.2522 (pooled 0.2442, delta_brier=+0.0080)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3765 auc=0.619 (pooled 0.551, delta_auc=+0.068) brier=0.2418 (pooled 0.2442, delta_brier=-0.0024)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4396] — oof_n=3660 auc=0.635 brier=0.2347
- **INFO** lc[n=7034] — oof_n=5860 auc=0.533 brier=0.2598
- **INFO** lc[n=9672] — oof_n=8060 auc=0.537 brier=0.2623
- **INFO** lc[n=12310] — oof_n=10255 auc=0.510 brier=0.2724
- **INFO** lc[n=14948] — oof_n=12455 auc=0.602 brier=0.2443
- **INFO** lc[n=17586] — oof_n=14655 auc=0.608 brier=0.2442
- **INFO** learning curve trend — FLAT (|delta_auc=+0.021| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 25.2% (n=17586) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 25.5% (n=17586) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 25.5% (n=17586) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=17586) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=17586) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=17586) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 0 failed (117s)

Corpus: live history (17586 rows)
