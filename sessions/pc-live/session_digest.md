# Session digest

**Verdict: SD-007 audit chain broken**

- Window: 2026-07-10 07:53 UTC -> 2026-10-24 12:32 UTC (2548.64h, ~1162 cycles)
- Equity (current capital epoch): $800.00 -> $737.95 (range $69.16) | 5 epochs lifetime, range $99,262.28 | realized PnL (post-close-fee) $-41.64 | fees (all legs) $51.82
- Activity: 2 open | 559 live labeled trades | 38111 candidates | 476 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 559 | cold=False
- Audit: 95113 main-chain records (2308 off-chain fork rows excluded from counts) (38415 non-routine) | dominant SZ-047 (58% of non-routine) | chain=TAMPER(first_break=97362) | retrain_requests 286
- Liquidity: spoofy 0% of non-liquid cycles | feed errors 275
- Recent (48h lens): 0 audit records | dominant None (0% of non-routine) | retrain_requests 0 | spoofy 0% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (100 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '12-10d4d0c2': 299, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1561 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 38670 rows on disk): 2026-07-13T12:35:47Z -> 2026-10-09T19:54:13Z (88.3d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [ERR]  **SD-007 audit chain broken**  -  hash chain first breaks at record 97362  -  a record was edited or removed (own-hash mismatch or dangling prev) past that point
- [WARN] **SD-011 audit fork carries divergent payloads**  -  1738 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 439, 'SZ-051': 402, 'ML-070': 401, 'FW-050': 312, 'OM-040': 307, 'LB-050': 287, 'CX-030': 284, 'CV-010': 244, 'SZ-049': 199, 'FT-020': 173, 'CG-000': 163, 'ML-031': 150, 'OM-000': 94, 'CV-030': 78, 'EN-000': 69, 'SZ-052': 51, 'ML-016': 46, 'ML-042': 44, 'CV-000': 42, 'ML-041': 41, 'PT-061': 32, 'ML-032': 27, 'ML-030': 19, 'LB-000': 16, 'RT-010': 15, 'FT-010': 14, 'SZ-053': 11, 'ML-076': 7, 'ML-050': 6, 'LB-021': 6, 'ML-040': 5, 'SZ-048': 3, 'SZ-047': 2, 'SZ-046': 2, 'LB-020': 2, 'OM-080': 1, 'OM-013': 1, 'RP-070': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '12-10d4d0c2': 299, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
