# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 11:32 UTC (1131.66h, ~254 cycles)
- Equity (current capital epoch): $800.00 -> $802.67 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $5.23 | fees $6.78
- Activity: 4 open | 364 live labeled trades | 16907 candidates | 304 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 364 | cold=False
- Audit: 68722 records (29309 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 150
- Liquidity: spoofy 63% of classified cycles | feed errors 0
- Recent (48h lens): 442 audit records | dominant LB-010 (18% of non-routine) | retrain_requests 6 | spoofy 63%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 63% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
