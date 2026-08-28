# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-28 17:34 UTC (1185.69h, ~2774 cycles)
- Equity (current capital epoch): $800.00 -> $798.48 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL $2.88 | fees $8.14
- Activity: 5 open | 375 live labeled trades | 18561 candidates | 313 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 375 | cold=False
- Audit: 69502 records (29940 non-routine) | dominant SZ-047 (74% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 159
- Liquidity: spoofy 66% of classified cycles | feed errors 1
- Recent (48h lens): 676 audit records | dominant LB-010 (36% of non-routine) | retrain_requests 8 | spoofy 66%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 66% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 36% of 551 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
