# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-19 20:26 UTC (972.54h, ~2632 cycles)
- Equity: $25,000.00 -> $804.55 (range $99,208.70) | realized PnL $6.37 | fees $4.31
- Activity: 0 open | 342 live labeled trades | 12241 candidates | 285 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 342 | cold=False
- Audit: 45827 records (28059 non-routine) | dominant SZ-047 (79% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 125
- Liquidity: spoofy 69% of classified cycles | feed errors 0
- Recent (48h lens): 363 audit records | dominant OM-000 (14% of non-routine) | retrain_requests 6 | spoofy 69%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 69% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
