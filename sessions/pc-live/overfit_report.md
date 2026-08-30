# Overfit audit — 2026-08-30 21:28 UTC

Dataset: live history (10357 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.798 oof_auc=0.501 gap=+0.297; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.828 oof_auc=0.512 gap=+0.316; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.774 oof_auc=0.512 gap=+0.262; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3363 vs base-rate constant 0.2488 (base=0.465, n=8630) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2510 vs base-rate constant 0.2488 (base=0.465, n=8630) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3106 vs base-rate constant 0.2488 (base=0.465, n=8630) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=161.8 (10357 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=385); mixed-sample dsr=0.000 sr=-0.39; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1886 (candidate=1874 live=12) base_rate=0.360
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (12 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1484 auc=0.620 (pooled 0.512, delta_auc=+0.108) brier=0.2340 (pooled 0.2510, delta_brier=-0.0170)
- **INFO** regime[bull_vol] — n=1355 (candidate=1345 live=10) base_rate=0.461
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1333 auc=0.565 (pooled 0.512, delta_auc=+0.053) brier=0.2411 (pooled 0.2510, delta_brier=-0.0099)
- **INFO** regime[range] — n=8944 (candidate=8638 live=306) base_rate=0.262
- **INFO** regime[range] oof — oof_n=1765 auc=0.553 (pooled 0.512, delta_auc=+0.041) brier=0.2446 (pooled 0.2510, delta_brier=-0.0064)
- **INFO** regime[bear] — n=6354 (candidate=6297 live=57) base_rate=0.320
- **INFO** regime[bear] oof — oof_n=1861 auc=0.498 (pooled 0.512, delta_auc=-0.014) brier=0.2501 (pooled 0.2510, delta_brier=-0.0009)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.537 (pooled 0.512, delta_auc=+0.025) brier=0.2744 (pooled 0.2510, delta_brier=+0.0235)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2589] — oof_n=2155 auc=0.449 brier=0.2703
- **INFO** lc[n=4143] — oof_n=3450 auc=0.635 brier=0.2307
- **INFO** lc[n=5696] — oof_n=4745 auc=0.604 brier=0.2485
- **INFO** lc[n=7250] — oof_n=6040 auc=0.523 brier=0.2565
- **INFO** lc[n=8803] — oof_n=7335 auc=0.523 brier=0.2614
- **INFO** lc[n=10357] — oof_n=8630 auc=0.555 brier=0.2510
- **INFO** learning curve trend — FLAT (|delta_auc=-0.003| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 38.2% (n=10357) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 38.6% (n=10357) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 38.6% (n=10357) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.9% (n=10357) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=10357) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=10357) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (52s)

Corpus: live history (10357 rows)
