# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 18:32 UTC (1114.65h, ~1786 cycles)
- Equity: $25,000.00 -> $803.15 (range $99,208.70) | realized PnL $5.02 | fees $6.40
- Activity: 4 open | 361 live labeled trades | 16478 candidates | 302 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 361 | cold=False
- Audit: 68541 records (29139 non-routine) | dominant SZ-047 (76% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 148
- Liquidity: spoofy 54% of classified cycles | feed errors 0
- Recent (48h lens): 384 audit records | dominant ML-031 (14% of non-routine) | retrain_requests 7 | spoofy 54%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 54% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
