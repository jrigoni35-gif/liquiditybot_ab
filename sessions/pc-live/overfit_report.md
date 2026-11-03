# Overfit audit — 2026-11-03 08:00 UTC

Dataset: live history (28077 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.732 oof_auc=0.551 gap=+0.181; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.770 oof_auc=0.565 gap=+0.206; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.766 oof_auc=0.540 gap=+0.227; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2684 vs base-rate constant 0.2424 (base=0.413, n=23395) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2624 vs base-rate constant 0.2424 (base=0.413, n=23395) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2788 vs base-rate constant 0.2424 (base=0.413, n=23395) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.499 z=0.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **FAIL** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.67 over 6 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.57 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.074, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=412.9 (28077 rows / 68 features)
- **INFO** dof EFFECTIVE n (report-only; the gate above reads NOMINAL) — rows/feature nominal=412.90 vs effective=1.49 (n=28077 -> n_eff=101.4, mean uniqueness 0.004); an SE on nominal n is optimistic by x16.64. Route: asset-blind (lower bound on n_eff) — the floor of 10 is NOT applied to it and nothing here moves PASS/FAIL.
- **INFO** dof EFFECTIVE n — THE OTHER ROUTE (read the PAIR) — per-asset rows/feature=28.99 (n_eff=1971.0, from the production loader's own mean_uniqueness, which keys concurrency per (asset, 5m bar) as this seam cannot). The routes differ by x19.4 on the SAME corpus and NEITHER is adjudicated — asset-blind is a lower bound, per-asset an upper. Quote the PAIR with its routes, never one number.
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 38/68 features (30 of the 56 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.82 (56 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['depth_log', 'mom_dir', 'funding_dir', 'vol_percentile', 'hour_cos', 'liq_pocket_pull'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=1/n null fallback)
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample — dsr=0.004 sr=-0.23 n=43 sr0=0.211 (probes excluded: 516)
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR(SR*=0)=0.084 -> P(true SR < 0)=0.916. This, NOT the graded dsr, is the 'is the edge positive' number - dsr is P(true SR > sr0) where sr0 is the expected max under the null across N trials. A red dsr beside a PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: 43 conviction trips spanning 2026-07-20..2026-10-09 (81.1 days). NOT era-scoped: signal_history.csv has no exec_era column (the stamp lives in core/fill_ledger.py, keyed by position_id), so this sample pools every execution era it covers - different fee bookings AND different barrier geometries. CLAUDE.md: trips are 'citable AS their era, none poolable across a cut'. Read the verdict against THIS span, not against the deployed config.
- **PASS** dsr: deployed-era regression sentinel — era=12-10d4d0c2 n=13 n_eff=8.3 mean=$-0.172/trip total=$-2.24 ub95=$+0.393 (one-sided 95%, z=1.645) MDE=$-0.565/trip - NO LOSS DEMONSTRATED AT THIS SENSITIVITY. That is NOT an all-clear, and it says NOTHING about why OF-5's pooled gate is red: this test can only resolve a mean worse than $-0.565/trip, against a registered H0 bleed of about -$0.27/trip. Read it as 'not yet decidable', and read the MDE before quoting this line. [19 conviction trip(s) EXCLUDED (impure_era=19); $-18.91 of PnL is not in this statistic - an exclusion that removes losers is itself a silencing channel, so read this count]
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=9515 (candidate=9424 live=91) base_rate=0.407
- **INFO** regime[bull_quiet] oof — oof_n=8824 auc=0.516 (pooled 0.565, delta_auc=-0.049) brier=0.2585 (pooled 0.2624, delta_brier=-0.0039)
- **INFO** regime[bull_vol] — n=1910 (candidate=1895 live=15) base_rate=0.449
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (15 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1864 auc=0.514 (pooled 0.565, delta_auc=-0.051) brier=0.2754 (pooled 0.2624, delta_brier=+0.0130)
- **INFO** regime[range] — n=14019 (candidate=13643 live=376) base_rate=0.312
- **INFO** regime[range] oof — oof_n=6503 auc=0.533 (pooled 0.565, delta_auc=-0.032) brier=0.2626 (pooled 0.2624, delta_brier=+0.0002)
- **INFO** regime[bear] — n=8708 (candidate=8631 live=77) base_rate=0.375
- **INFO** regime[bear] oof — oof_n=3665 auc=0.507 (pooled 0.565, delta_auc=-0.058) brier=0.2660 (pooled 0.2624, delta_brier=+0.0036)
- **INFO** regime[crisis] — n=4566 (candidate=4566 live=0) base_rate=0.422
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2539 auc=0.461 (pooled 0.565, delta_auc=-0.104) brier=0.2609 (pooled 0.2624, delta_brier=-0.0015)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=7019] — oof_n=5845 auc=0.530 brier=0.2629
- **INFO** lc[n=11231] — oof_n=9355 auc=0.489 brier=0.2710
- **INFO** lc[n=15442] — oof_n=12865 auc=0.586 brier=0.2451
- **INFO** lc[n=19654] — oof_n=16375 auc=0.534 brier=0.2579
- **INFO** lc[n=23865] — oof_n=19885 auc=0.539 brier=0.2717
- **INFO** lc[n=28077] — oof_n=23395 auc=0.520 brier=0.2624
- **INFO** learning curve trend — FLAT (|delta_auc=+0.020| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 23.4% (n=28077) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 23.6% (n=28077) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 23.6% (n=28077) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 1.9% (n=28077) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=28077) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 1.1% (n=28077) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 2 failed (193s)

Corpus: live history (28077 rows)
