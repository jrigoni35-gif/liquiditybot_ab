# Session digest

**Verdict: SD-004 audit trail dominated by one code**

- Window: 2026-07-10 07:53 UTC -> 2026-08-30 06:35 UTC (1222.7h, ~5 cycles)
- Equity (current capital epoch): $800.00 -> $798.22 (range $10.12) | 5 epochs lifetime, range $99,208.70 | realized PnL (post-close-fee) $1.72 | fees (all legs) $8.72
- Activity: 5 open | 378 live labeled trades | 19166 candidates | 316 postmortems
- Model: level 1 | use_model=True | brier n/a | history_rows 378 | cold=False
- Audit: 70106 records (30373 non-routine) | dominant SZ-047 (73% of non-routine) | chain=SEAMS(9, benign) | retrain_requests 165
- Liquidity: spoofy 83% of non-liquid cycles | feed errors 0
- Recent (48h lens): 749 audit records | dominant LB-010 (35% of non-routine) | retrain_requests 8 | spoofy 83% (non-liquid)

## Diagnostics
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 35% of 550 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  9 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
