# Session digest

**Verdict: SD-011 audit fork carries divergent payloads**

- Window: 2026-07-10 07:53 UTC -> 2026-09-01 21:37 UTC (1285.74h, ~1033 cycles)
- Equity (current capital epoch): $800.00 -> $793.13 (range $14.33) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $-1.69 | fees (all legs) $10.62
- Activity: 2 open | 391 live labeled trades | 22049 candidates | 328 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 391 | cold=False
- Audit: 75427 records (30955 non-routine) | dominant SZ-047 (72% of non-routine) | chain=SEAMS(10, benign) | retrain_requests 174
- Liquidity: spoofy 60% of non-liquid cycles | feed errors 2
- Recent (48h lens): 5080 audit records | dominant LB-010 (25% of non-routine) | retrain_requests 7 | spoofy 60% (non-liquid)

## Diagnostics
- [WARN] **SD-011 audit fork carries divergent payloads**  -  38 duplicated seq(s) whose rows disagree on (code, hash) - codes riding forks: {'ML-031': 9, 'OM-000': 8, 'SZ-051': 7, 'ML-030': 7, 'CV-030': 6, 'SZ-053': 6, 'LB-010': 5, 'ML-050': 4, 'CG-000': 3, 'RT-010': 3, 'FT-020': 3, 'ML-070': 3, 'SZ-047': 2, 'SZ-049': 2, 'OM-040': 2, 'FT-010': 1, 'ML-076': 1, 'OM-080': 1, 'ML-016': 1, 'ML-042': 1, 'ML-041': 1}; first examples: [{'seq': 503, 'codes': ['CG-000', 'RT-010'], 'ts': [1784239154.313, 1784239173.189]}, {'seq': 14864, 'codes': ['CG-000', 'SZ-047'], 'ts': [1785150021.206, 1785150150.318]}, {'seq': 14865, 'codes': ['FT-020', 'SZ-047'], 'ts': [1785150035.288, 1785150150.333]}]. Instruments consuming audit rows must not treat forked-seq rows as unique venue truth; find the writer (an unredirected script/harness - configure_audit exists for exactly this) and quarantine, never delete
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 60% of NON-LIQUID cycles (last 48h; liquid cycles are unlogged, so this is a share of degraded cycles, not of all cycles - cross-check status regimes for absolute prevalence). Spoofy suppresses sizing/taker on the affected asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  10 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
