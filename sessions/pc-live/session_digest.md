# Session digest

**Verdict: SD-010 audit writer seam(s)**

- Window: 2026-07-10 07:53 UTC -> 2026-08-20 22:28 UTC (998.58h, ~133 cycles)
- Equity: $25,000.00 -> $804.69 (range $99,208.70) | realized PnL $6.81 | fees $4.45
- Activity: 3 open | 343 live labeled trades | 12809 candidates | 287 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 343 | cold=False
- Audit: 52669 records (28210 non-routine) | dominant SZ-047 (79% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 129
- Liquidity: spoofy 49% of classified cycles | feed errors 0
- Recent (48h lens): 7082 audit records | dominant ML-031 (12% of non-routine) | retrain_requests 7 | spoofy 49%

## Diagnostics
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
