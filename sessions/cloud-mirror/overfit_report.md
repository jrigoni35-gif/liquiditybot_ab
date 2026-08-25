# Overfit audit — 2026-08-22 21:23 UTC

Dataset: live history (4215 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.802 oof_auc=0.563 gap=+0.239; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.879 oof_auc=0.630 gap=+0.249; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.830 oof_auc=0.618 gap=+0.211; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3276 vs base-rate constant 0.2468 (base=0.557, n=3510) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2357 vs base-rate constant 0.2468 (base=0.557, n=3510) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3368 vs base-rate constant 0.2468 (base=0.557, n=3510) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.504 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=65.9 (4215 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.81 (52 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_mom_dir', 'funding_dir', 'weekend', 'th_grid', 'ret_1_dir', 'ret_6_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=346); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=570 (candidate=563 live=7) base_rate=0.398
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=374 auc=0.348 (pooled 0.630, delta_auc=-0.282) brier=0.2977 (pooled 0.2357, delta_brier=+0.0619)
- **INFO** regime[bull_quiet] FLAG — OOF materially degrades vs pooled (delta_auc=-0.282, worse than the -0.12 margin OF-1 uses for its own train/OOF gap)
- **INFO** regime[bull_vol] — n=29 (candidate=29 live=0) base_rate=0.586
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=17 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=7371 (candidate=7083 live=288) base_rate=0.226
- **INFO** regime[range] oof — oof_n=407 auc=0.521 (pooled 0.630, delta_auc=-0.109) brier=0.2626 (pooled 0.2357, delta_brier=+0.0269)
- **INFO** regime[bear] — n=5009 (candidate=4958 live=51) base_rate=0.297
- **INFO** regime[bear] oof — oof_n=1155 auc=0.435 (pooled 0.630, delta_auc=-0.195) brier=0.2740 (pooled 0.2357, delta_brier=+0.0383)
- **INFO** regime[bear] FLAG — OOF materially degrades vs pooled (delta_auc=-0.195, worse than the -0.12 margin OF-1 uses for its own train/OOF gap)
- **INFO** regime[crisis] — n=1560 (candidate=1560 live=0) base_rate=0.601
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=1557 auc=0.729 (pooled 0.630, delta_auc=+0.099) brier=0.1856 (pooled 0.2357, delta_brier=-0.0501)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=1054] — oof_n=875 auc=0.435 brier=0.2809
- **INFO** lc[n=1686] — oof_n=1405 auc=0.588 brier=0.2435
- **INFO** lc[n=2318] — oof_n=1930 auc=0.529 brier=0.2638
- **INFO** lc[n=2950] — oof_n=2455 auc=0.469 brier=0.2558
- **INFO** lc[n=3583] — oof_n=2985 auc=0.539 brier=0.2625
- **INFO** lc[n=4215] — oof_n=3510 auc=0.616 brier=0.2357
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.066 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 31.9% (n=4215) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 32.8% (n=4215) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 32.8% (n=4215) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.9% (n=4215) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=4215) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=4215) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (66s)

Corpus: live history (4215 rows)
