# Overfit audit — 2026-08-27 21:12 UTC

Dataset: live history (7744 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.828 oof_auc=0.458 gap=+0.370; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.798 oof_auc=0.567 gap=+0.231; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.865 oof_auc=0.504 gap=+0.361; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3943 vs base-rate constant 0.2498 (base=0.512, n=6450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2399 vs base-rate constant 0.2498 (base=0.512, n=6450) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3244 vs base-rate constant 0.2498 (base=0.512, n=6450) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=121.0 (7744 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.98 (63 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at /home/user/liquiditybot_ab/outputs/trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=372); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1004 (candidate=995 live=9) base_rate=0.379
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=658 auc=0.684 (pooled 0.567, delta_auc=+0.117) brier=0.2420 (pooled 0.2399, delta_brier=+0.0021)
- **INFO** regime[bull_vol] — n=1052 (candidate=1043 live=9) base_rate=0.470
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=953 auc=0.500 (pooled 0.567, delta_auc=-0.067) brier=0.2480 (pooled 0.2399, delta_brier=+0.0081)
- **INFO** regime[range] — n=8226 (candidate=7928 live=298) base_rate=0.249
- **INFO** regime[range] oof — oof_n=1022 auc=0.604 (pooled 0.567, delta_auc=+0.037) brier=0.2393 (pooled 0.2399, delta_brier=-0.0006)
- **INFO** regime[bear] — n=5943 (candidate=5887 live=56) base_rate=0.325
- **INFO** regime[bear] oof — oof_n=1631 auc=0.629 (pooled 0.567, delta_auc=+0.062) brier=0.2351 (pooled 0.2399, delta_brier=-0.0048)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2186 auc=0.617 (pooled 0.567, delta_auc=+0.050) brier=0.2396 (pooled 0.2399, delta_brier=-0.0003)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=1936] — oof_n=1610 auc=0.552 brier=0.2557
- **INFO** lc[n=3098] — oof_n=2580 auc=0.579 brier=0.2426
- **INFO** lc[n=4259] — oof_n=3545 auc=0.628 brier=0.2351
- **INFO** lc[n=5421] — oof_n=4515 auc=0.590 brier=0.2500
- **INFO** lc[n=6582] — oof_n=5485 auc=0.556 brier=0.2540
- **INFO** lc[n=7744] — oof_n=6450 auc=0.643 brier=0.2399
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.034 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 27.8% (n=7744) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 28.2% (n=7744) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 28.2% (n=7744) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.2% (n=7744) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=7744) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=7744) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (61s)

Corpus: live history (7744 rows)
