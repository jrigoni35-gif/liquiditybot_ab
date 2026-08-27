# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-27 06:33 UTC (1150.67h, ~2010 cycles)
- Equity (current capital epoch): $800.00 -> $801.23 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $3.53 | fees $7.37
- Activity: 3 open | 369 live labeled trades | 17577 candidates | 308 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 369 | cold=False
- Audit: 69060 records (29557 non-routine) | dominant SZ-047 (75% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 153
- Liquidity: spoofy 54% of classified cycles | feed errors 0
- Recent (48h lens): 625 audit records | dominant LB-010 (28% of non-routine) | retrain_requests 7 | spoofy 54%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 54% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
