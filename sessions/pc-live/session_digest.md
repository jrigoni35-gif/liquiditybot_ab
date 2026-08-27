# Session digest

**Verdict: SD-003 liquidity vetoed feed-wide**

- Window: 2026-07-10 07:53 UTC -> 2026-08-27 16:33 UTC (1160.67h, ~3193 cycles)
- Equity (current capital epoch): $800.00 -> $802.99 (range $9.30) | 5 epochs lifetime, range $99,208.70 | realized PnL $3.69 | fees $7.55
- Activity: 3 open | 372 live labeled trades | 18030 candidates | 310 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 372 | cold=False
- Audit: 69187 records (29674 non-routine) | dominant SZ-047 (75% of non-routine) | chain=SEAMS(8, benign) | retrain_requests 155
- Liquidity: spoofy 56% of classified cycles | feed errors 0
- Recent (48h lens): 659 audit records | dominant LB-010 (31% of non-routine) | retrain_requests 7 | spoofy 56%

## Diagnostics
- [WARN] **SD-003 liquidity vetoed feed-wide**  -  liquidity classified 'spoofy' on 56% of classified cycles (last 48h), which suppresses sizing/taker on every asset. On a near-zero-spread feed this is likely a classifier miscalibration, not real spoofing  -  inspect the book source
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 31% of 548 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
