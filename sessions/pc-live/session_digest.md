# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-04 23:40 UTC (1359.78h, ~3495 cycles)
- Equity (current capital epoch): $800.00 -> $793.48 (range $16.78) | 5 epochs lifetime, range $99,209.90 | realized PnL (post-close-fee) $-0.55 | fees (all legs) $12.96
- Activity: 5 open | 407 live labeled trades | 24350 candidates | 342 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 407 | cold=False
- Audit: 77577 records (32023 non-routine) | dominant SZ-047 (70% of non-routine) | chain=SEAMS(11, benign) | retrain_requests 186
- Liquidity: spoofy 68% of non-liquid cycles | feed errors 3
- Recent (48h lens): 950 audit records | dominant LB-010 (21% of non-routine) | retrain_requests 8 | spoofy 68% (non-liquid)
- Eras: current 9-16ec821e | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1024, '7-e7d5ca1a': 133, '9-16ec821e': 61, '8-ca55e2ba': 10, 'absent(stale-binary)': 6, '4-aeeaae36': 4} (1238 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 24757 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-04T22:05:00Z (53.4d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  51 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'SZ-051': 11, 'ML-031': 10, 'OM-000': 9, 'ML-070': 7, 'ML-030': 7, 'LB-010': 7, 'CG-000': 6, 'CV-030': 6, 'SZ-053': 6, 'FT-020': 5, 'SZ-049': 5, 'ML-050': 4, 'RT-010': 3, 'OM-040': 3, 'SZ-047': 2, 'CX-030': 2, 'LB-050': 2, 'FT-010': 1, 'ML-076': 1, 'OM-080': 1, 'ML-016': 1, 'ML-042': 1, 'ML-041': 1, 'SZ-052': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  6 exec_era keys on fills.exec_era: {'prestamp': 1024, '7-e7d5ca1a': 133, '9-16ec821e': 61, '8-ca55e2ba': 10, 'absent(stale-binary)': 6, '4-aeeaae36': 4}; current era 9-16ec821e. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 68% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  11 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
