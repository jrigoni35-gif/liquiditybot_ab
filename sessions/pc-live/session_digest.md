# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-17 09:32 UTC (1657.65h, ~1047 cycles)
- Equity (current capital epoch): $800.00 -> $771.84 (range $35.44) | 5 epochs lifetime, range $99,228.56 | realized PnL (post-close-fee) $-17.38 | fees (all legs) $26.96
- Activity: 3 open | 458 live labeled trades | 29709 candidates | 388 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 458 | cold=False
- Audit: 89316 records (35779 non-routine) | dominant SZ-047 (62% of non-routine) | chain=SEAMS(61, benign) | retrain_requests 233
- Liquidity: spoofy 2% of non-liquid cycles | feed errors 4
- Recent (48h lens): 582 audit records | dominant LB-010 (21% of non-routine) | retrain_requests 7 | spoofy 2% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '12-10d4d0c2': 83, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1345 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 30167 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-17T04:30:00Z (65.66d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  1718 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 434, 'SZ-051': 402, 'ML-070': 401, 'FW-050': 312, 'OM-040': 307, 'LB-050': 287, 'CX-030': 284, 'CV-010': 244, 'SZ-049': 198, 'FT-020': 162, 'CG-000': 155, 'ML-031': 150, 'OM-000': 93, 'CV-030': 78, 'EN-000': 68, 'SZ-052': 51, 'ML-016': 46, 'ML-042': 44, 'ML-041': 41, 'CV-000': 40, 'PT-061': 32, 'ML-032': 27, 'ML-030': 19, 'LB-000': 16, 'SZ-053': 11, 'RT-010': 10, 'FT-010': 8, 'ML-076': 7, 'ML-050': 6, 'LB-021': 6, 'ML-040': 5, 'SZ-048': 3, 'SZ-047': 2, 'SZ-046': 2, 'LB-020': 2, 'OM-080': 1, 'OM-013': 1, 'RP-070': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '12-10d4d0c2': 83, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [INFO] **SD-010 audit writer seam(s)**  -  61 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
