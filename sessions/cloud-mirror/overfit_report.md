# Overfit audit — 2026-08-27 13:01 UTC

Dataset: live history (7629 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.829 oof_auc=0.451 gap=+0.378; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.841 oof_auc=0.588 gap=+0.254; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.854 oof_auc=0.533 gap=+0.321; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3925 vs base-rate constant 0.2499 (base=0.511, n=6355) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2413 vs base-rate constant 0.2499 (base=0.511, n=6355) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3310 vs base-rate constant 0.2499 (base=0.511, n=6355) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=119.2 (7629 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.89 (57 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'sigma_bar_pct', 'vol_percentile', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=371); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=969 (candidate=960 live=9) base_rate=0.380
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=628 auc=0.686 (pooled 0.588, delta_auc=+0.099) brier=0.2397 (pooled 0.2413, delta_brier=-0.0016)
- **INFO** regime[bull_vol] — n=1047 (candidate=1038 live=9) base_rate=0.470
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=946 auc=0.517 (pooled 0.588, delta_auc=-0.071) brier=0.2507 (pooled 0.2413, delta_brier=+0.0094)
- **INFO** regime[range] — n=8171 (candidate=7874 live=297) base_rate=0.246
- **INFO** regime[range] oof — oof_n=969 auc=0.597 (pooled 0.588, delta_auc=+0.010) brier=0.2417 (pooled 0.2413, delta_brier=+0.0004)
- **INFO** regime[bear] — n=5921 (candidate=5865 live=56) base_rate=0.323
- **INFO** regime[bear] oof — oof_n=1626 auc=0.620 (pooled 0.588, delta_auc=+0.032) brier=0.2385 (pooled 0.2413, delta_brier=-0.0028)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2186 auc=0.626 (pooled 0.588, delta_auc=+0.038) brier=0.2397 (pooled 0.2413, delta_brier=-0.0017)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=1907] — oof_n=1585 auc=0.559 brier=0.2570
- **INFO** lc[n=3052] — oof_n=2540 auc=0.562 brier=0.2513
- **INFO** lc[n=4196] — oof_n=3495 auc=0.607 brier=0.2381
- **INFO** lc[n=5340] — oof_n=4450 auc=0.592 brier=0.2580
- **INFO** lc[n=6485] — oof_n=5400 auc=0.586 brier=0.2483
- **INFO** lc[n=7629] — oof_n=6355 auc=0.641 brier=0.2413
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.053 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 27.9% (n=7629) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 28.3% (n=7629) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 28.3% (n=7629) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.1% (n=7629) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=7629) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=7629) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (64s)

Corpus: live history (7629 rows)
