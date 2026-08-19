# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-19 23:26 UTC (975.55h, ~88 cycles)
- Equity: $25,000.00 -> $804.96 (range $99,208.70) | realized PnL $6.81 | fees $4.37
- Activity: 0 open | 343 live labeled trades | 12393 candidates | 287 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 343 | cold=False
- Audit: 45845 records (28071 non-routine) | dominant SZ-047 (79% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 126
- Liquidity: spoofy 73% of classified cycles | feed errors 1
- Recent (48h lens): 370 audit records | dominant OM-000 (15% of non-routine) | retrain_requests 7 | spoofy 73%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 73% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
