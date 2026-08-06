# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-06 15:02 UTC (655.14h, ~1930 cycles)
- Equity: $25,000.00 -> $4,938.74 (range $99,208.70) | realized PnL $-43.83 | fees $62.47
- Activity: 3 open | 301 live labeled trades | 9342 candidates | 260 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 301 | cold=True
- Audit: 28954 records (26101 non-routine) | dominant SZ-047 (85% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 83
- Liquidity: spoofy 47% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=301, brier=n/a) yet retrain was requested 83x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 85% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 85% of 26101 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
