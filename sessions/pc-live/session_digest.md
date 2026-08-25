# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 21:32 UTC (1117.65h, ~2059 cycles)
- Equity: $25,000.00 -> $802.58 (range $99,208.70) | realized PnL $5.02 | fees $6.45
- Activity: 5 open | 361 live labeled trades | 16682 candidates | 302 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 361 | cold=False
- Audit: 68566 records (29162 non-routine) | dominant SZ-047 (76% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 148
- Liquidity: spoofy 55% of classified cycles | feed errors 1
- Recent (48h lens): 400 audit records | dominant CV-030 (14% of non-routine) | retrain_requests 7 | spoofy 55%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 55% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
