# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 00:31 UTC (1096.63h, ~3259 cycles)
- Equity: $25,000.00 -> $803.70 (range $99,208.70) | realized PnL $5.20 | fees $6.07
- Activity: 3 open | 358 live labeled trades | 15957 candidates | 300 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 358 | cold=False
- Audit: 68378 records (29046 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 146
- Liquidity: spoofy 55% of classified cycles | feed errors 0
- Recent (48h lens): 1144 audit records | dominant ML-031 (14% of non-routine) | retrain_requests 8 | spoofy 55%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 55% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
