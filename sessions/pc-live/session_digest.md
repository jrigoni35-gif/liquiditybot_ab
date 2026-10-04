# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-10-04 21:29 UTC (2077.6h, ~895 cycles)
- Equity (current capital epoch): $800.00 -> $751.29 (range $57.12) | 5 epochs lifetime, range $99,250.24 | realized PnL (post-close-fee) $-32.76 | fees (all legs) $45.96
- Activity: 5 open | 533 live labeled trades | 36043 candidates | 452 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 533 | cold=False
- Audit: 93499 main-chain records (2241 off-chain fork rows excluded from counts) (37112 non-routine) | dominant SZ-047 (60% of non-routine) | chain=SEAMS(63, benign) | retrain_requests 284
- Liquidity: spoofy 3% of non-liquid cycles | feed errors 0
- Recent (48h lens): 702 audit records | dominant LB-010 (34% of non-routine) | retrain_requests 5 | spoofy 3% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (100 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '12-10d4d0c2': 249, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1511 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 36576 rows on disk): 2026-07-13T12:35:47Z -> 2026-10-04T07:20:00Z (82.78d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  1721 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 434, 'SZ-051': 402, 'ML-070': 401, 'FW-050': 312, 'OM-040': 307, 'LB-050': 287, 'CX-030': 284, 'CV-010': 244, 'SZ-049': 198, 'FT-020': 164, 'CG-000': 156, 'ML-031': 150, 'OM-000': 93, 'CV-030': 78, 'EN-000': 69, 'SZ-052': 51, 'ML-016': 46, 'ML-042': 44, 'ML-041': 41, 'CV-000': 40, 'PT-061': 32, 'ML-032': 27, 'ML-030': 19, 'LB-000': 16, 'RT-010': 11, 'SZ-053': 11, 'FT-010': 9, 'ML-076': 7, 'ML-050': 6, 'LB-021': 6, 'ML-040': 5, 'SZ-048': 3, 'SZ-047': 2, 'SZ-046': 2, 'LB-020': 2, 'OM-080': 1, 'OM-013': 1, 'RP-070': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '12-10d4d0c2': 249, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 34% of 580 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  63 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
