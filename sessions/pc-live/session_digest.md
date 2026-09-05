# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-05 08:40 UTC (1368.79h, ~1028 cycles)
- Equity (current capital epoch): $800.00 -> $793.19 (range $16.78) | 5 epochs lifetime, range $99,209.90 | realized PnL (post-close-fee) $-0.55 | fees (all legs) $12.96
- Activity: 5 open | 407 live labeled trades | 24561 candidates | 342 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 407 | cold=False
- Audit: 77737 records (32183 non-routine) | dominant SZ-047 (69% of non-routine) | chain=SEAMS(12, benign) | retrain_requests 187
- Liquidity: spoofy 75% of non-liquid cycles | feed errors 0
- Recent (48h lens): 1029 audit records | dominant LB-010 (20% of non-routine) | retrain_requests 7 | spoofy 75% (non-liquid)
- Eras: current 9-16ec821e | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1024, '7-e7d5ca1a': 133, '9-16ec821e': 61, '8-ca55e2ba': 10, 'absent(stale-binary)': 6, '4-aeeaae36': 4} (1238 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 24968 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-05T07:40:00Z (53.79d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  176 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 72, 'CX-030': 62, 'LB-050': 62, 'CG-000': 30, 'FT-020': 30, 'SZ-049': 21, 'ML-031': 17, 'OM-000': 14, 'CV-030': 12, 'SZ-051': 11, 'ML-070': 7, 'ML-030': 7, 'SZ-053': 6, 'ML-016': 6, 'ML-042': 6, 'ML-041': 6, 'ML-050': 4, 'RT-010': 3, 'OM-040': 3, 'SZ-047': 2, 'FT-010': 1, 'ML-076': 1, 'OM-080': 1, 'SZ-052': 1, 'ML-032': 1, 'LB-000': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  6 exec_era keys on fills.exec_era: {'prestamp': 1024, '7-e7d5ca1a': 133, '9-16ec821e': 61, '8-ca55e2ba': 10, 'absent(stale-binary)': 6, '4-aeeaae36': 4}; current era 9-16ec821e. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 75% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  12 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
