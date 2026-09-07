# Overfit audit — 2026-09-07 19:39 UTC

Dataset: live history (16487 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.770 oof_auc=0.549 gap=+0.221; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.802 oof_auc=0.551 gap=+0.251; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.794 oof_auc=0.538 gap=+0.255; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2757 vs base-rate constant 0.2469 (base=0.444, n=13735) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2494 vs base-rate constant 0.2469 (base=0.444, n=13735) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3082 vs base-rate constant 0.2469 (base=0.444, n=13735) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.495 z=1.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=257.6 (16487 rows / 64 features)
- **INFO** dof coverage — fitted GBT consulted 55/64 features - dead read taken on a model that actually looked
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.80 (51 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['funding_dir', 'direction', 'pat_hammer_dir', 'spread_bps', 'hour_cos', 'fv_edge_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=415); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3394 (candidate=3372 live=22) base_rate=0.408
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (22 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=2813 auc=0.576 (pooled 0.551, delta_auc=+0.025) brier=0.2540 (pooled 0.2494, delta_brier=+0.0046)
- **INFO** regime[bull_vol] — n=1736 (candidate=1723 live=13) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1711 auc=0.581 (pooled 0.551, delta_auc=+0.030) brier=0.2443 (pooled 0.2494, delta_brier=-0.0051)
- **INFO** regime[range] — n=10610 (candidate=10293 live=317) base_rate=0.301
- **INFO** regime[range] oof — oof_n=3229 auc=0.618 (pooled 0.551, delta_auc=+0.067) brier=0.2405 (pooled 0.2494, delta_brier=-0.0089)
- **INFO** regime[bear] — n=7230 (candidate=7167 live=63) base_rate=0.339
- **INFO** regime[bear] oof — oof_n=2230 auc=0.548 (pooled 0.551, delta_auc=-0.003) brier=0.2644 (pooled 0.2494, delta_brier=+0.0150)
- **INFO** regime[crisis] — n=3923 (candidate=3923 live=0) base_rate=0.453
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3752 auc=0.618 (pooled 0.551, delta_auc=+0.067) brier=0.2471 (pooled 0.2494, delta_brier=-0.0023)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4122] — oof_n=3435 auc=0.638 brier=0.2265
- **INFO** lc[n=6595] — oof_n=5495 auc=0.558 brier=0.2533
- **INFO** lc[n=9068] — oof_n=7555 auc=0.515 brier=0.2798
- **INFO** lc[n=11541] — oof_n=9615 auc=0.501 brier=0.2608
- **INFO** lc[n=14014] — oof_n=11675 auc=0.551 brier=0.2644
- **INFO** lc[n=16487] — oof_n=13735 auc=0.596 brier=0.2494
- **INFO** learning curve trend — FLAT (|delta_auc=-0.025| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 26.8% (n=16487) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 27.2% (n=16487) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 27.2% (n=16487) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=16487) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=16487) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=16487) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (96s)

Corpus: live history (16487 rows)
