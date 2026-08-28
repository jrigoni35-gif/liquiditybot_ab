# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-28 11:34 UTC (1179.68h, ~2066 cycles)
- Equity (current capital epoch): $800.00 -> $801.49 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $2.88 | fees $8.00
- Activity: 4 open | 375 live labeled trades | 18316 candidates | 313 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 375 | cold=False
- Audit: 69419 records (29874 non-routine) | dominant SZ-047 (74% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 158
- Liquidity: spoofy 63% of classified cycles | feed errors 1
- Recent (48h lens): 697 audit records | dominant LB-010 (35% of non-routine) | retrain_requests 8 | spoofy 63%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 63% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 35% of 565 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
