# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-24 21:31 UTC (1093.63h, ~2932 cycles)
- Equity: $25,000.00 -> $803.58 (range $99,208.70) | realized PnL $5.18 | fees $6.03
- Activity: 4 open | 357 live labeled trades | 15902 candidates | 299 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 357 | cold=False
- Audit: 68366 records (29036 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 145
- Liquidity: spoofy 56% of classified cycles | feed errors 0
- Recent (48h lens): 1944 audit records | dominant ML-031 (13% of non-routine) | retrain_requests 8 | spoofy 56%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
