# Overfit audit — 2026-08-19 00:03 UTC

Dataset: live history (1003 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.828 oof_auc=0.564 gap=+0.263; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.795 oof_auc=0.482 gap=+0.313; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.832 oof_auc=0.569 gap=+0.264; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3498 vs base-rate constant 0.1751 (base=0.226, n=835) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2652 vs base-rate constant 0.1751 (base=0.226, n=835) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3681 vs base-rate constant 0.1751 (base=0.226, n=835) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.481 z=1.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=15.7 (1003 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.48 (31 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_12_dir', 'hour_sin', 'basis_dir', 'regime_age', 'corr_fast', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 24 conviction-marked live trades < 30 (mixed n=333); mixed-sample dsr=0.000 sr=-0.47; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=270 (candidate=266 live=4) base_rate=0.163
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=156 auc=0.412 (pooled 0.482, delta_auc=-0.070) brier=0.2668 (pooled 0.2652, delta_brier=+0.0016)
- **INFO** regime[bull_vol] — n=12 (candidate=12 live=0) base_rate=0.250
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=0 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6991 (candidate=6710 live=281) base_rate=0.207
- **INFO** regime[range] oof — oof_n=281 auc=0.470 (pooled 0.482, delta_auc=-0.011) brier=0.2507 (pooled 0.2652, delta_brier=-0.0146)
- **INFO** regime[bear] — n=4039 (candidate=3991 live=48) base_rate=0.227
- **INFO** regime[bear] oof — oof_n=398 auc=0.421 (pooled 0.482, delta_auc=-0.061) brier=0.2749 (pooled 0.2652, delta_brier=+0.0097)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=251] — oof_n=82 auc=0.364 brier=0.2504
- **INFO** lc[n=401] — oof_n=264 auc=0.389 brier=0.2423
- **INFO** lc[n=552] — oof_n=368 auc=0.423 brier=0.2727
- **INFO** lc[n=702] — oof_n=468 auc=0.442 brier=0.2677
- **INFO** lc[n=853] — oof_n=710 auc=0.416 brier=0.2738
- **INFO** lc[n=1003] — oof_n=835 auc=0.435 brier=0.2652
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.049 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 87.9% (n=1003)
- **INFO** extras[opt_pcr_z] — at-neutral share 87.9% (n=1003)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 87.9% (n=1003)
- **INFO** extras[dominance_delta] — at-neutral share 7.7% (n=1003) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1003) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1003) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (47s)

Corpus: live history (1003 rows)
