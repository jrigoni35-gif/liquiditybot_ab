# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-19 01:25 UTC (953.54h, ~391 cycles)
- Equity: $25,000.00 -> $799.72 (range $99,208.70) | realized PnL $0.53 | fees $3.45
- Activity: 5 open | 334 live labeled trades | 11074 candidates | 284 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 334 | cold=False
- Audit: 45610 records (27937 non-routine) | dominant SZ-047 (80% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 122
- Liquidity: spoofy 68% of classified cycles | feed errors 0
- Recent (48h lens): 407 audit records | dominant OM-040 (19% of non-routine) | retrain_requests 5 | spoofy 68%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 68% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
