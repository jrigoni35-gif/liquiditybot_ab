# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-05 23:41 UTC (1383.8h, ~2763 cycles)
- Equity (current capital epoch): $800.00 -> $793.63 (range $16.78) | 5 epochs lifetime, range $99,209.90 | realized PnL (post-close-fee) $-0.86 | fees (all legs) $13.79
- Activity: 4 open | 410 live labeled trades | 24845 candidates | 345 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 410 | cold=False
- Audit: 77898 records (32317 non-routine) | dominant SZ-047 (69% of non-routine) | chain=SEAMS(16, benign) | retrain_requests 193
- Liquidity: spoofy 78% of non-liquid cycles | feed errors 3
- Recent (48h lens): 982 audit records | dominant LB-010 (17% of non-routine) | retrain_requests 11 | spoofy 78% (non-liquid)
- Eras: current 9-16ec821e | signal_history exec_era: unavailable (signal_history.csv has no exec_era column (95 columns; label_era present=True, a label-definition axis, not the execution era)) | fills per exec_era: {'prestamp': 1024, '7-e7d5ca1a': 133, '9-16ec821e': 66, '8-ca55e2ba': 10, 'absent(stale-binary)': 6, '4-aeeaae36': 4} (1243 rows) | pooling_hazard=True (source fills.exec_era)
- RAW signal-file span (signal_ts, all 25255 rows on disk): 2026-07-13T12:35:47Z -> 2026-09-05T21:30:00Z (54.37d) - NOT the TRAINED corpus span: era exclusion + the label_era filter drop rows, so the span the champion is SCORED on is shorter. For that one (the MinBTL / Sharpe-SE denominator) run scripts/champion_skill_report.py --json -> corpus_span_days

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  223 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'LB-010': 112, 'CX-030': 73, 'LB-050': 73, 'CV-030': 44, 'CG-000': 36, 'FT-020': 36, 'ML-031': 32, 'SZ-051': 24, 'SZ-049': 23, 'OM-000': 22, 'ML-070': 20, 'ML-030': 19, 'ML-016': 12, 'ML-042': 12, 'ML-041': 12, 'ML-032': 7, 'OM-040': 6, 'ML-050': 6, 'SZ-053': 6, 'LB-000': 4, 'RT-010': 3, 'PT-061': 3, 'SZ-047': 2, 'SZ-052': 2, 'FT-010': 1, 'ML-076': 1, 'OM-080': 1, 'SZ-046': 1, 'OM-013': 1, 'LB-021': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-012 rows from more than one execution era share one file**  -  6 exec_era keys on fills.exec_era: {'prestamp': 1024, '7-e7d5ca1a': 133, '9-16ec821e': 66, '8-ca55e2ba': 10, 'absent(stale-binary)': 6, '4-aeeaae36': 4}; current era 9-16ec821e. Do NOT pool across eras (CLAUDE.md accrual moratorium) - any statistic over this file must segment by exec_era first (signal_history.csv exec_era: ABSENT - segment by ts against the boundary table)
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 78% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  16 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
