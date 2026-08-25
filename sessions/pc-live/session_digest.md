# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 23:32 UTC (1119.65h, ~2167 cycles)
- Equity (current capital epoch): $800.00 -> $802.90 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $5.28 | fees $6.52
- Activity: 4 open | 362 live labeled trades | 16694 candidates | 302 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 362 | cold=False
- Audit: 68586 records (29182 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 149
- Liquidity: spoofy 54% of classified cycles | feed errors 2
- Recent (48h lens): 386 audit records | dominant CV-030 (14% of non-routine) | retrain_requests 7 | spoofy 54%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 54% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
