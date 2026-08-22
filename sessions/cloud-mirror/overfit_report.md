# Overfit audit — 2026-08-22 16:30 UTC

Dataset: live history (4141 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.804 oof_auc=0.539 gap=+0.265; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.856 oof_auc=0.605 gap=+0.251; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.795 oof_auc=0.590 gap=+0.205; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3438 vs base-rate constant 0.2463 (base=0.561, n=3450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2328 vs base-rate constant 0.2463 (base=0.561, n=3450) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3458 vs base-rate constant 0.2463 (base=0.561, n=3450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.493 z=1.4 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=64.7 (4141 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.72 (46 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['pat_hammer_dir', 'vol_term', 'spread_bps', 'basis_dir', 'ret_6_dir', 'corr_fast'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=346); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=570 (candidate=563 live=7) base_rate=0.398
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=376 auc=0.325 (pooled 0.605, delta_auc=-0.279) brier=0.3063 (pooled 0.2328, delta_brier=+0.0736)
- **INFO** regime[bull_quiet] FLAG — OOF materially degrades vs pooled (delta_auc=-0.279, worse than the -0.12 margin OF-1 uses for its own train/OOF gap)
- **INFO** regime[bull_vol] — n=29 (candidate=29 live=0) base_rate=0.586
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=17 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=7371 (candidate=7083 live=288) base_rate=0.226
- **INFO** regime[range] oof — oof_n=407 auc=0.575 (pooled 0.605, delta_auc=-0.030) brier=0.2528 (pooled 0.2328, delta_brier=+0.0200)
- **INFO** regime[bear] — n=5009 (candidate=4958 live=51) base_rate=0.297
- **INFO** regime[bear] oof — oof_n=1165 auc=0.470 (pooled 0.605, delta_auc=-0.135) brier=0.2662 (pooled 0.2328, delta_brier=+0.0334)
- **INFO** regime[bear] FLAG — OOF materially degrades vs pooled (delta_auc=-0.135, worse than the -0.12 margin OF-1 uses for its own train/OOF gap)
- **INFO** regime[crisis] — n=1486 (candidate=1486 live=0) base_rate=0.613
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=1485 auc=0.721 (pooled 0.605, delta_auc=+0.116) brier=0.1829 (pooled 0.2328, delta_brier=-0.0499)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=1035] — oof_n=860 auc=0.443 brier=0.2746
- **INFO** lc[n=1656] — oof_n=1380 auc=0.655 brier=0.2439
- **INFO** lc[n=2278] — oof_n=1895 auc=0.523 brier=0.2625
- **INFO** lc[n=2899] — oof_n=2415 auc=0.566 brier=0.2496
- **INFO** lc[n=3520] — oof_n=2930 auc=0.604 brier=0.2409
- **INFO** lc[n=4141] — oof_n=3450 auc=0.625 brier=0.2328
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.066 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 32.5% (n=4141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 33.4% (n=4141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 33.4% (n=4141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 4.0% (n=4141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=4141) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=4141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (42s)

Corpus: live history (4141 rows)
