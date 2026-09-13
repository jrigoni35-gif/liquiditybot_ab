# Overfit audit — 2026-09-13 20:18 UTC

Dataset: live history (18544 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.756 oof_auc=0.545 gap=+0.211; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.796 oof_auc=0.527 gap=+0.268; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.737 oof_auc=0.534 gap=+0.203; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2642 vs base-rate constant 0.2433 (base=0.418, n=15450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2488 vs base-rate constant 0.2433 (base=0.418, n=15450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2904 vs base-rate constant 0.2433 (base=0.418, n=15450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.27 over 6 configs / 70 splits (mean winner: gbt_d2_lr10)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.26 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.135, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=289.8 (18544 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 14/64 features (50 of the 54 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.84 (54 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=1/n null fallback)
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample — dsr=0.005 sr=-0.26 n=31 sr0=0.249 (probes excluded: 409)
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR(SR*=0)=0.091 -> P(true SR < 0)=0.909. This, NOT the graded dsr, is the 'is the edge positive' number - dsr is P(true SR > sr0) where sr0 is the expected max under the null across N trials. A red dsr beside a PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: 31 conviction trips spanning 2026-07-20..2026-09-13 (54.9 days). NOT era-scoped: signal_history.csv has no exec_era column (the stamp lives in core/fill_ledger.py, keyed by position_id), so this sample pools every execution era it covers - different fee bookings AND different barrier geometries. CLAUDE.md: trips are 'citable AS their era, none poolable across a cut'. Read the verdict against THIS span, not against the deployed config.
- **INFO** dsr: deployed-era regression sentinel — DEFERRED - 1 conviction trips wholly inside era 12-10d4d0c2 < 10. The deployed configuration is not yet separately measurable; OF-5's pooled verdict says NOTHING about it either way. [19 conviction trip(s) EXCLUDED (impure_era=19); $-18.91 of PnL is not in this statistic - an exclusion that removes losers is itself a silencing channel, so read this count]
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=4282 (candidate=4250 live=32) base_rate=0.386
- **INFO** regime[bull_quiet] oof — oof_n=3689 auc=0.550 (pooled 0.527, delta_auc=+0.023) brier=0.2500 (pooled 0.2488, delta_brier=+0.0013)
- **INFO** regime[bull_vol] — n=1804 (candidate=1790 live=14) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (14 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1778 auc=0.609 (pooled 0.527, delta_auc=+0.082) brier=0.2395 (pooled 0.2488, delta_brier=-0.0093)
- **INFO** regime[range] — n=11417 (candidate=11087 live=330) base_rate=0.296
- **INFO** regime[range] oof — oof_n=4013 auc=0.604 (pooled 0.527, delta_auc=+0.076) brier=0.2448 (pooled 0.2488, delta_brier=-0.0039)
- **INFO** regime[bear] — n=7360 (candidate=7296 live=64) base_rate=0.344
- **INFO** regime[bear] oof — oof_n=2364 auc=0.518 (pooled 0.527, delta_auc=-0.009) brier=0.2647 (pooled 0.2488, delta_brier=+0.0159)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3606 auc=0.616 (pooled 0.527, delta_auc=+0.088) brier=0.2460 (pooled 0.2488, delta_brier=-0.0028)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4636] — oof_n=3860 auc=0.607 brier=0.2487
- **INFO** lc[n=7418] — oof_n=6180 auc=0.552 brier=0.2558
- **INFO** lc[n=10199] — oof_n=8495 auc=0.541 brier=0.2511
- **INFO** lc[n=12981] — oof_n=10815 auc=0.553 brier=0.2560
- **INFO** lc[n=15762] — oof_n=13135 auc=0.602 brier=0.2478
- **INFO** lc[n=18544] — oof_n=15450 auc=0.587 brier=0.2488
- **INFO** learning curve trend — FLAT (|delta_auc=+0.015| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 24.0% (n=18544) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 24.3% (n=18544) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 24.3% (n=18544) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.2% (n=18544) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=18544) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=18544) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 1 failed (130s)

Corpus: live history (18544 rows)
