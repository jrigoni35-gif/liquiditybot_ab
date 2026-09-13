# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-13 15:28 UTC (1567.58h, ~561 cycles)
- Equity (current capital epoch): $800.00 -> $782.59 (range $24.56) | 5 epochs lifetime, range $99,217.68 | realized PnL (post-close-fee) $-8.23 | fees (all legs) $21.97
- Activity: 3 open | 439 live labeled trades | 28502 candidates | 371 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 439 | cold=False
- Audit: 88326 records (35103 non-routine) | dominant SZ-047 (63% of non-routine) | chain=SEAMS(60, benign) | retrain_requests 219
- Liquidity: spoofy 0% of non-liquid cycles | feed errors 1
- Recent (48h lens): 531 audit records | dominant ML-031 (18% of non-routine) | retrain_requests 8 | spoofy 0% (non-liquid)
- Eras: current 12-10d4d0c2 | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '12-10d4d0c2': 42, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4} (1304 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 28941 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-13T09:45:00Z (61.88d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  1249 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 382, 'SZ-051': 309, 'ML-070': 305, 'LB-050': 241, 'FW-050': 240, 'CX-030': 238, 'OM-040': 184, 'CV-010': 160, 'SZ-049': 156, 'FT-020': 135, 'CG-000': 128, 'ML-031': 102, 'CV-030': 75, 'OM-000': 66, 'SZ-052': 37, 'CV-000': 31, 'ML-016': 30, 'ML-042': 29, 'ML-041': 27, 'PT-061': 21, 'ML-030': 19, 'ML-032': 19, 'EN-000': 16, 'RT-010': 10, 'LB-000': 10, 'FT-010': 8, 'ML-076': 7, 'SZ-053': 7, 'ML-050': 6, 'LB-021': 3, 'ML-040': 3, 'SZ-047': 2, 'OM-080': 1, 'SZ-046': 1, 'OM-013': 1, 'LB-020': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  8 exec_era keys on fills.exec_era: {'prestamp': 1030, '7-e7d5ca1a': 133, '9-16ec821e': 68, '12-10d4d0c2': 42, '8-ca55e2ba': 10, '10-a5acfe2d': 9, '11-6e584923': 8, '4-aeeaae36': 4}; current era 12-10d4d0c2. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [INFO] **SD-010 audit writer seam(s)**  -  60 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
