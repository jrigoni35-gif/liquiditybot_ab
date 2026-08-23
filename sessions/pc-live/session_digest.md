# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-23 13:30 UTC (1061.62h, ~2230 cycles)
- Equity: $25,000.00 -> $803.17 (range $99,208.70) | realized PnL $5.13 | fees $5.40
- Activity: 2 open | 353 live labeled trades | 14936 candidates | 295 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 353 | cold=False
- Audit: 68136 records (28861 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 140
- Liquidity: spoofy 67% of classified cycles | feed errors 6
- Recent (48h lens): 11433 audit records | dominant LB-010 (30% of non-routine) | retrain_requests 8 | spoofy 67%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 67% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
