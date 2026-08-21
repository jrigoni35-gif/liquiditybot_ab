# Overfit audit — 2026-08-21 21:42 UTC

Dataset: live history (3785 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.799 oof_auc=0.442 gap=+0.358; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.814 oof_auc=0.597 gap=+0.217; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.829 oof_auc=0.558 gap=+0.271; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3860 vs base-rate constant 0.2471 (base=0.554, n=3150) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2218 vs base-rate constant 0.2471 (base=0.554, n=3150) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3468 vs base-rate constant 0.2471 (base=0.554, n=3150) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.507 z=1.4 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=59.1 (3785 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.84 (54 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['other_ret_6_dir', 'poc_dist', 'va_pos', 'mkt_ret_6_dir', 'funding_dist', 'th_grid'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=346); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=570 (candidate=563 live=7) base_rate=0.398
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=377 auc=0.297 (pooled 0.597, delta_auc=-0.300) brier=0.2798 (pooled 0.2218, delta_brier=+0.0580)
- **INFO** regime[bull_quiet] FLAG — OOF materially degrades vs pooled (delta_auc=-0.300, worse than the -0.12 margin OF-1 uses for its own train/OOF gap)
- **INFO** regime[bull_vol] — n=29 (candidate=29 live=0) base_rate=0.586
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=17 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=7371 (candidate=7083 live=288) base_rate=0.226
- **INFO** regime[range] oof — oof_n=449 auc=0.482 (pooled 0.597, delta_auc=-0.115) brier=0.2632 (pooled 0.2218, delta_brier=+0.0414)
- **INFO** regime[bear] — n=5009 (candidate=4958 live=51) base_rate=0.297
- **INFO** regime[bear] oof — oof_n=1182 auc=0.447 (pooled 0.597, delta_auc=-0.150) brier=0.2601 (pooled 0.2218, delta_brier=+0.0383)
- **INFO** regime[bear] FLAG — OOF materially degrades vs pooled (delta_auc=-0.150, worse than the -0.12 margin OF-1 uses for its own train/OOF gap)
- **INFO** regime[crisis] — n=1130 (candidate=1130 live=0) base_rate=0.630
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=1125 auc=0.777 (pooled 0.597, delta_auc=+0.180) brier=0.1475 (pooled 0.2218, delta_brier=-0.0744)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=946] — oof_n=785 auc=0.469 brier=0.2616
- **INFO** lc[n=1514] — oof_n=1260 auc=0.635 brier=0.2529
- **INFO** lc[n=2082] — oof_n=1735 auc=0.502 brier=0.2704
- **INFO** lc[n=2650] — oof_n=2205 auc=0.517 brier=0.2612
- **INFO** lc[n=3217] — oof_n=2680 auc=0.628 brier=0.2358
- **INFO** lc[n=3785] — oof_n=3150 auc=0.657 brier=0.2218
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.090 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 35.5% (n=3785) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 36.5% (n=3785) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 36.5% (n=3785) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 4.2% (n=3785) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=3785) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=3785) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (45s)

Corpus: live history (3785 rows)
