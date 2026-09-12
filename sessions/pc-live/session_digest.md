# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-12 02:30 UTC (1530.62h, ~1377 cycles)
- Equity (current capital epoch): $800.00 -> $787.16 (range $23.82) | 5 epochs lifetime, range $99,216.94 | realized PnL (post-close-fee) $-3.90 | fees (all legs) $20.20
- Activity: 4 open | 434 live labeled trades | 27991 candidates | 366 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 434 | cold=False
- Audit: 87833 records (34889 non-routine) | dominant SZ-047 (64% of non-routine) | chain=SEAMS(59, benign) | retrain_requests 213
- Liquidity: spoofy 1% of non-liquid cycles | feed errors 8
- Recent (48h lens): 1967 audit records | dominant LB-010 (15% of non-routine) | retrain_requests 8 | spoofy 2% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '12-10d4d0c2': 31, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1293 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 28425 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-11T17:55:00Z (60.22d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  766 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 306, 'LB-050': 199, 'CX-030': 196, 'SZ-051': 183, 'ML-070': 179, 'FW-050': 154, 'FT-020': 113, 'SZ-049': 112, 'CG-000': 106, 'CV-010': 73, 'ML-031': 68, 'OM-040': 56, 'CV-030': 50, 'OM-000': 45, 'ML-016': 22, 'ML-042': 21, 'ML-041': 21, 'ML-030': 19, 'CV-000': 19, 'PT-061': 16, 'ML-032': 13, 'RT-010': 10, 'SZ-052': 10, 'FT-010': 8, 'SZ-053': 7, 'LB-000': 7, 'ML-076': 6, 'ML-050': 6, 'SZ-047': 2, 'LB-021': 2, 'OM-080': 1, 'SZ-046': 1, 'OM-013': 1, 'ML-040': 1, 'LB-020': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '12-10d4d0c2': 31, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [INFO] **SD-010 audit writer seam(s)**  -  59 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
