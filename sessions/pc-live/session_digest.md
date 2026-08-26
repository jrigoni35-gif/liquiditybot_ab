# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 12:32 UTC (1132.66h, ~351 cycles)
- Equity (current capital epoch): $800.00 -> $802.14 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $5.23 | fees $6.85
- Activity: 5 open | 364 live labeled trades | 16913 candidates | 304 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 364 | cold=False
- Audit: 68748 records (29324 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 150
- Liquidity: spoofy 66% of classified cycles | feed errors 0
- Recent (48h lens): 446 audit records | dominant LB-010 (19% of non-routine) | retrain_requests 6 | spoofy 66%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 66% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
