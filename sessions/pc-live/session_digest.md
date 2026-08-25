# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 17:32 UTC (1113.64h, ~1683 cycles)
- Equity: $25,000.00 -> $802.85 (range $99,208.70) | realized PnL $5.02 | fees $6.40
- Activity: 4 open | 361 live labeled trades | 16474 candidates | 302 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 361 | cold=False
- Audit: 68534 records (29132 non-routine) | dominant SZ-047 (76% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 148
- Liquidity: spoofy 54% of classified cycles | feed errors 0
- Recent (48h lens): 378 audit records | dominant ML-031 (15% of non-routine) | retrain_requests 7 | spoofy 54%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 54% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
