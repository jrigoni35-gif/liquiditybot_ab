# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-24 19:31 UTC (1091.63h, ~2695 cycles)
- Equity: $25,000.00 -> $803.43 (range $99,208.70) | realized PnL $5.18 | fees $6.00
- Activity: 3 open | 357 live labeled trades | 15899 candidates | 299 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 357 | cold=False
- Audit: 68342 records (29031 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 145
- Liquidity: spoofy 55% of classified cycles | feed errors 0
- Recent (48h lens): 2632 audit records | dominant LB-010 (12% of non-routine) | retrain_requests 8 | spoofy 55%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 55% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
