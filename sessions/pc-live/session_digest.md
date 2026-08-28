# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-28 06:34 UTC (1174.68h, ~1476 cycles)
- Equity (current capital epoch): $800.00 -> $801.41 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $2.88 | fees $7.85
- Activity: 3 open | 375 live labeled trades | 18292 candidates | 313 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 375 | cold=False
- Audit: 69357 records (29823 non-routine) | dominant SZ-047 (75% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 157
- Liquidity: spoofy 56% of classified cycles | feed errors 1
- Recent (48h lens): 707 audit records | dominant LB-010 (34% of non-routine) | retrain_requests 7 | spoofy 56%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 34% of 579 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
