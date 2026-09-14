# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-14 19:30 UTC (1595.61h, ~1369 cycles)
- Equity (current capital epoch): $800.00 -> $782.55 (range $26.55) | 5 epochs lifetime, range $99,219.67 | realized PnL (post-close-fee) $-8.52 | fees (all legs) $23.83
- Activity: 4 open | 445 live labeled trades | 28841 candidates | 376 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 445 | cold=False
- Audit: 88645 records (35244 non-routine) | dominant SZ-047 (63% of non-routine) | chain=SEAMS(60, benign) | retrain_requests 224
- Liquidity: spoofy 2% of non-liquid cycles | feed errors 8
- Recent (48h lens): 631 audit records | dominant ML-031 (15% of non-routine) | retrain_requests 8 | spoofy 2% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '12-10d4d0c2': 56, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1318 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 29286 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-14T17:10:00Z (63.19d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  1568 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 400, 'SZ-051': 393, 'ML-070': 389, 'FW-050': 309, 'OM-040': 283, 'LB-050': 259, 'CX-030': 256, 'CV-010': 233, 'SZ-049': 176, 'FT-020': 146, 'CG-000': 139, 'ML-031': 130, 'OM-000': 82, 'CV-030': 77, 'SZ-052': 47, 'EN-000': 45, 'ML-016': 38, 'ML-042': 37, 'ML-041': 34, 'CV-000': 32, 'PT-061': 27, 'ML-032': 24, 'ML-030': 19, 'LB-000': 13, 'SZ-053': 11, 'RT-010': 10, 'FT-010': 8, 'ML-076': 7, 'ML-050': 6, 'LB-021': 5, 'ML-040': 4, 'SZ-047': 2, 'SZ-046': 2, 'LB-020': 2, 'OM-080': 1, 'OM-013': 1, 'RP-070': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '12-10d4d0c2': 56, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [INFO] **SD-010 audit writer seam(s)**  -  60 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
