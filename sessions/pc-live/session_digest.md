# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-24 23:19 UTC (1839.43h, ~1865 cycles)
- Equity (current capital epoch): $800.00 -> $763.93 (range $44.82) | 5 epochs lifetime, range $99,237.94 | realized PnL (post-close-fee) $-21.53 | fees (all legs) $35.72
- Activity: 4 open | 494 live labeled trades | 32333 candidates | 419 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 494 | cold=False
- Audit: 90827 records (36892 non-routine) | dominant SZ-047 (60% of non-routine) | chain=SEAMS(63, benign) | retrain_requests 262
- Liquidity: spoofy 5% of non-liquid cycles | feed errors 6
- Recent (48h lens): 428 audit records | dominant EN-000 (16% of non-routine) | retrain_requests 7 | spoofy 4% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (100 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '12-10d4d0c2': 167, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1429 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 32827 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-24T18:50:00Z (73.26d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  1721 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 434, 'SZ-051': 402, 'ML-070': 401, 'FW-050': 312, 'OM-040': 307, 'LB-050': 287, 'CX-030': 284, 'CV-010': 244, 'SZ-049': 198, 'FT-020': 164, 'CG-000': 156, 'ML-031': 150, 'OM-000': 93, 'CV-030': 78, 'EN-000': 69, 'SZ-052': 51, 'ML-016': 46, 'ML-042': 44, 'ML-041': 41, 'CV-000': 40, 'PT-061': 32, 'ML-032': 27, 'ML-030': 19, 'LB-000': 16, 'RT-010': 11, 'SZ-053': 11, 'FT-010': 9, 'ML-076': 7, 'ML-050': 6, 'LB-021': 6, 'ML-040': 5, 'SZ-048': 3, 'SZ-047': 2, 'SZ-046': 2, 'LB-020': 2, 'OM-080': 1, 'OM-013': 1, 'RP-070': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '12-10d4d0c2': 167, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [INFO] **SD-010 audit writer seam(s)**  -  63 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
