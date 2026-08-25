# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-25 13:32 UTC (1109.64h, ~1280 cycles)
- Equity: $25,000.00 -> $802.86 (range $99,208.70) | realized PnL $4.93 | fees $6.32
- Activity: 4 open | 360 live labeled trades | 16395 candidates | 302 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 360 | cold=False
- Audit: 68476 records (29096 non-routine) | dominant SZ-047 (76% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 147
- Liquidity: spoofy 50% of classified cycles | feed errors 0
- Recent (48h lens): 340 audit records | dominant ML-031 (17% of non-routine) | retrain_requests 7 | spoofy 50%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 50% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
