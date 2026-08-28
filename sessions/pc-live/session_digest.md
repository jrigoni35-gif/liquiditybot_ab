# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-28 20:34 UTC (1188.68h, ~3127 cycles)
- Equity (current capital epoch): $800.00 -> $797.42 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL $2.88 | fees $8.14
- Activity: 5 open | 375 live labeled trades | 18694 candidates | 313 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 375 | cold=False
- Audit: 69535 records (29973 non-routine) | dominant SZ-047 (74% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 159
- Liquidity: spoofy 65% of classified cycles | feed errors 1
- Recent (48h lens): 622 audit records | dominant LB-010 (37% of non-routine) | retrain_requests 8 | spoofy 65%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 65% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 37% of 540 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
