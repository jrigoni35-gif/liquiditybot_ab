# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-23 07:30 UTC (1055.61h, ~1582 cycles)
- Equity: $25,000.00 -> $803.22 (range $99,208.70) | realized PnL $5.88 | fees $5.17
- Activity: 4 open | 350 live labeled trades | 14683 candidates | 293 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 350 | cold=False
- Audit: 68099 records (28838 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 139
- Liquidity: spoofy 66% of classified cycles | feed errors 6
- Recent (48h lens): 12995 audit records | dominant LB-010 (32% of non-routine) | retrain_requests 8 | spoofy 66%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 66% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 32% of 513 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
