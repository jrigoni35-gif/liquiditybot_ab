# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-21 01:28 UTC (1001.58h, ~476 cycles)
- Equity: $25,000.00 -> $805.12 (range $99,208.70) | realized PnL $6.89 | fees $4.53
- Activity: 1 open | 345 live labeled trades | 12902 candidates | 288 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 345 | cold=False
- Audit: 53033 records (28252 non-routine) | dominant SZ-047 (79% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 130
- Liquidity: spoofy 50% of classified cycles | feed errors 1
- Recent (48h lens): 7423 audit records | dominant ML-031 (12% of non-routine) | retrain_requests 8 | spoofy 50%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 50% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
