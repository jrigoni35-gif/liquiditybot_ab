# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 23:33 UTC (1143.66h, ~1404 cycles)
- Equity (current capital epoch): $800.00 -> $802.53 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $4.26 | fees $7.15
- Activity: 4 open | 367 live labeled trades | 17476 candidates | 306 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 367 | cold=False
- Audit: 68961 records (29474 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 152
- Liquidity: spoofy 56% of classified cycles | feed errors 0
- Recent (48h lens): 591 audit records | dominant LB-010 (25% of non-routine) | retrain_requests 7 | spoofy 56%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
