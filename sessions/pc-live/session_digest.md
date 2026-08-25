# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 06:32 UTC (1102.64h, ~593 cycles)
- Equity: $25,000.00 -> $804.66 (range $99,208.70) | realized PnL $5.22 | fees $6.25
- Activity: 4 open | 359 live labeled trades | 16149 candidates | 301 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 359 | cold=False
- Audit: 68435 records (29074 non-routine) | dominant SZ-047 (77% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 146
- Liquidity: spoofy 54% of classified cycles | feed errors 0
- Recent (48h lens): 338 audit records | dominant ML-031 (18% of non-routine) | retrain_requests 7 | spoofy 54%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 54% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
