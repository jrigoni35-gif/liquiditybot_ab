# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-19 11:25 UTC (963.54h, ~1574 cycles)
- Equity: $25,000.00 -> $799.92 (range $99,208.70) | realized PnL $0.80 | fees $3.60
- Activity: 3 open | 336 live labeled trades | 11454 candidates | 285 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 336 | cold=False
- Audit: 45659 records (27984 non-routine) | dominant SZ-047 (80% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 124
- Liquidity: spoofy 76% of classified cycles | feed errors 0
- Recent (48h lens): 445 audit records | dominant OM-040 (15% of non-routine) | retrain_requests 7 | spoofy 76%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 76% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
