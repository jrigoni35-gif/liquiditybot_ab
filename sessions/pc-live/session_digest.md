# Session digest

**Verdict: SD-004 audit trail dominated by one code**

- Window: 2026-07-10 07:53 UTC -> 2026-08-22 17:30 UTC (1041.61h, ~84 cycles)
- Equity: $25,000.00 -> $805.04 (range $99,208.70) | realized PnL $6.96 | fees $4.58
- Activity: 0 open | 346 live labeled trades | 14130 candidates | 290 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 346 | cold=False
- Audit: 65060 records (28665 non-routine) | dominant SZ-047 (78% of non-routine) | chain_ok=False (tamper=False, seams=8) | retrain_requests 137
- Liquidity: spoofy 50% of classified cycles | feed errors 0
- Recent (48h lens): 13858 audit records | dominant LB-010 (34% of non-routine) | retrain_requests 8 | spoofy 50%

## Diagnostics
- [WARN] **SD-004 audit trail dominated by one code**  -  LB-010 is 34% of 524 non-routine records (last 48h)  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  8 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
