# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-23 05:30 UTC (1053.61h, ~1394 cycles)
- Equity: $25,000.00 -> $803.29 (range $99,208.70) | realized PnL $5.88 | fees $5.14
- Activity: 3 open | 350 live labeled trades | 14674 candidates | 292 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 350 | cold=False
- Audit: 68081 records (28830 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 139
- Liquidity: spoofy 67% of classified cycles | feed errors 1
- Recent (48h lens): 13765 audit records | dominant LB-010 (33% of non-routine) | retrain_requests 8 | spoofy 67%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 67% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 33% of 529 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
