# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 22:33 UTC (1142.66h, ~1309 cycles)
- Equity (current capital epoch): $800.00 -> $802.56 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $4.10 | fees $7.08
- Activity: 5 open | 366 live labeled trades | 17452 candidates | 306 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 366 | cold=False
- Audit: 68946 records (29459 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 152
- Liquidity: spoofy 57% of classified cycles | feed errors 0
- Recent (48h lens): 579 audit records | dominant LB-010 (25% of non-routine) | retrain_requests 7 | spoofy 57%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 57% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
