# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-22 00:29 UTC (1024.6h, ~545 cycles)
- Equity: $25,000.00 -> $805.04 (range $99,208.70) | realized PnL $6.96 | fees $4.58
- Activity: 0 open | 346 live labeled trades | 13868 candidates | 290 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 346 | cold=False
- Audit: 59820 records (28501 non-routine) | dominant SZ-047 (78% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 134
- Liquidity: spoofy 62% of classified cycles | feed errors 0
- Recent (48h lens): 13974 audit records | dominant LB-010 (30% of non-routine) | retrain_requests 8 | spoofy 62%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 62% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
