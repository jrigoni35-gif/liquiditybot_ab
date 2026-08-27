# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-27 10:33 UTC (1154.67h, ~2483 cycles)
- Equity (current capital epoch): $800.00 -> $802.24 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $3.61 | fees $7.48
- Activity: 3 open | 371 live labeled trades | 17901 candidates | 310 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 371 | cold=False
- Audit: 69113 records (29605 non-routine) | dominant SZ-047 (75% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 154
- Liquidity: spoofy 55% of classified cycles | feed errors 0
- Recent (48h lens): 654 audit records | dominant LB-010 (30% of non-routine) | retrain_requests 7 | spoofy 55%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 55% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
