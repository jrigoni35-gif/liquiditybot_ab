# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 22:32 UTC (1118.65h, ~2144 cycles)
- Equity: $25,000.00 -> $802.89 (range $99,208.70) | realized PnL $5.28 | fees $6.52
- Activity: 4 open | 362 live labeled trades | 16689 candidates | 302 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 362 | cold=False
- Audit: 68578 records (29174 non-routine) | dominant SZ-047 (76% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 149
- Liquidity: spoofy 55% of classified cycles | feed errors 1
- Recent (48h lens): 390 audit records | dominant CV-030 (14% of non-routine) | retrain_requests 8 | spoofy 55%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 55% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
