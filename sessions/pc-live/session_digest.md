# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-19 18:26 UTC (970.54h, ~2395 cycles)
- Equity: $25,000.00 -> $804.93 (range $99,208.70) | realized PnL $6.86 | fees $4.24
- Activity: 2 open | 340 live labeled trades | 12206 candidates | 285 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 340 | cold=False
- Audit: 45802 records (28049 non-routine) | dominant SZ-047 (79% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 125
- Liquidity: spoofy 71% of classified cycles | feed errors 0
- Recent (48h lens): 438 audit records | dominant OM-000 (14% of non-routine) | retrain_requests 7 | spoofy 71%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 71% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
