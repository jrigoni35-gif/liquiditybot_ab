# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-28 02:34 UTC (1170.68h, ~1011 cycles)
- Equity (current capital epoch): $800.00 -> $801.56 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $3.37 | fees $7.74
- Activity: 3 open | 374 live labeled trades | 18234 candidates | 312 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 374 | cold=False
- Audit: 69288 records (29761 non-routine) | dominant SZ-047 (75% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 156
- Liquidity: spoofy 56% of classified cycles | feed errors 1
- Recent (48h lens): 681 audit records | dominant LB-010 (35% of non-routine) | retrain_requests 7 | spoofy 56%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 35% of 560 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
