# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 08:32 UTC (1128.65h, ~2824 cycles)
- Equity (current capital epoch): $800.00 -> $802.84 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $5.15 | fees $6.71
- Activity: 5 open | 363 live labeled trades | 16802 candidates | 303 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 363 | cold=False
- Audit: 68683 records (29270 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 150
- Liquidity: spoofy 53% of classified cycles | feed errors 2
- Recent (48h lens): 431 audit records | dominant LB-010 (17% of non-routine) | retrain_requests 7 | spoofy 53%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 53% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
