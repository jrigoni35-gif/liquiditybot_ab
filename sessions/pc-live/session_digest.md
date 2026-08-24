# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-24 02:31 UTC (1074.63h, ~900 cycles)
- Equity: $25,000.00 -> $803.22 (range $99,208.70) | realized PnL $5.31 | fees $5.59
- Activity: 3 open | 354 live labeled trades | 15367 candidates | 296 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 354 | cold=False
- Audit: 68213 records (28910 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 142
- Liquidity: spoofy 53% of classified cycles | feed errors 0
- Recent (48h lens): 7825 audit records | dominant LB-010 (23% of non-routine) | retrain_requests 8 | spoofy 53%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 53% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
