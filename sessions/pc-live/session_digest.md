# Session digest

**Verdict: SD-010 audit writer seam(s)**

- Window: 2026-07-10 07:53 UTC -> 2026-08-31 09:36 UTC (1249.72h, ~39 cycles)
- Equity (current capital epoch): $800.00 -> $795.86 (range $12.30) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $-0.24 | fees (all legs) $10.13
- Activity: 4 open | 387 live labeled trades | 20732 candidates | 324 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 387 | cold=False
- Audit: 70453 records (30667 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(10, benign) | retrain_requests 169
- Liquidity: spoofy 47% of non-liquid cycles | feed errors 197
- Recent (48h lens): 760 audit records | dominant LB-010 (29% of non-routine) | retrain_requests 8 | spoofy 47% (non-liquid)

## Diagnostics
- [INFO] **SD-010 audit writer seam(s)**  -  10 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
