# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-08 22:44 UTC (1454.84h, ~1 cycles)
- Equity (current capital epoch): $800.00 -> $788.26 (range $20.12) | 5 epochs lifetime, range $99,213.24 | realized PnL (post-close-fee) $-2.52 | fees (all legs) $16.16
- Activity: 5 open | 418 live labeled trades | 26976 candidates | 353 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 418 | cold=False
- Audit: 85718 records (32916 non-routine) | dominant SZ-047 (68% of non-routine) | chain=SEAMS(16, benign) | retrain_requests 204
- Liquidity: spoofy 0% of non-liquid cycles | feed errors 0
- Recent (48h lens): 1323 audit records | dominant LB-010 (25% of non-routine) | retrain_requests 8 | spoofy 0% (non-liquid)
- Eras: current 11-6e584923 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1262 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 27394 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-08T18:25:00Z (57.24d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  492 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'SZ-051': 150, 'ML-070': 146, 'LB-010': 143, 'LB-050': 103, 'CX-030': 100, 'FW-050': 90, 'CG-000': 49, 'FT-020': 49, 'SZ-049': 47, 'CV-030': 45, 'CV-010': 36, 'ML-031': 34, 'OM-000': 24, 'ML-030': 19, 'OM-040': 18, 'ML-016': 13, 'ML-042': 13, 'ML-041': 13, 'ML-032': 7, 'ML-050': 6, 'SZ-053': 6, 'PT-061': 5, 'LB-000': 4, 'RT-010': 3, 'SZ-047': 2, 'SZ-052': 2, 'FT-010': 1, 'ML-076': 1, 'OM-080': 1, 'SZ-046': 1, 'OM-013': 1, 'LB-021': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  7 exec_era keys on fills.exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 11-6e584923. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [INFO] **SD-010 audit writer seam(s)**  -  16 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
