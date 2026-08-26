# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 17:33 UTC (1137.66h, ~882 cycles)
- Equity (current capital epoch): $800.00 -> $801.52 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $4.10 | fees $6.99
- Activity: 3 open | 366 live labeled trades | 17233 candidates | 306 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 366 | cold=False
- Audit: 68826 records (29389 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 151
- Liquidity: spoofy 60% of classified cycles | feed errors 0
- Recent (48h lens): 491 audit records | dominant LB-010 (23% of non-routine) | retrain_requests 7 | spoofy 60%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 60% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
