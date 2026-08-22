# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-22 23:30 UTC (1047.61h, ~705 cycles)
- Equity: $25,000.00 -> $805.04 (range $99,208.70) | realized PnL $6.96 | fees $4.58
- Activity: 0 open | 346 live labeled trades | 14280 candidates | 290 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 346 | cold=False
- Audit: 66967 records (28736 non-routine) | dominant SZ-047 (78% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 138
- Liquidity: spoofy 66% of classified cycles | feed errors 1
- Recent (48h lens): 14280 audit records | dominant LB-010 (37% of non-routine) | retrain_requests 8 | spoofy 66%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 66% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 37% of 508 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
