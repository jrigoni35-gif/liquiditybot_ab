# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-26 10:32 UTC (1130.65h, ~136 cycles)
- Equity (current capital epoch): $800.00 -> $802.50 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $5.23 | fees $6.78
- Activity: 4 open | 364 live labeled trades | 16885 candidates | 303 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 364 | cold=False
- Audit: 68711 records (29298 non-routine) | dominant SZ-047 (76% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 150
- Liquidity: spoofy 64% of classified cycles | feed errors 0
- Recent (48h lens): 437 audit records | dominant LB-010 (18% of non-routine) | retrain_requests 7 | spoofy 64%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 64% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
