# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-24 03:31 UTC (1075.63h, ~1019 cycles)
- Equity: $25,000.00 -> $802.87 (range $99,208.70) | realized PnL $5.31 | fees $5.63
- Activity: 3 open | 354 live labeled trades | 15368 candidates | 296 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 354 | cold=False
- Audit: 68215 records (28912 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 142
- Liquidity: spoofy 52% of classified cycles | feed errors 0
- Recent (48h lens): 7439 audit records | dominant LB-010 (23% of non-routine) | retrain_requests 8 | spoofy 52%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 52% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
