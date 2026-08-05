# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-08-05 05:00 UTC (621.11h, ~1225 cycles)
- Equity: $25,000.00 -> $4,931.32 (range $99,208.70) | realized PnL $-44.04 | fees $61.19
- Activity: 5 open | 295 live labeled trades | 9113 candidates | 254 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 295 | cold=True
- Audit: 28590 records (25837 non-routine) | dominant SZ-047 (86% of non-routine) | chain_ok=False (tamper=False, seams=6) | retrain_requests 78
- Liquidity: spoofy 38% of classified cycles | feed errors 2

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=295, brier=n/a) yet retrain was requested 78x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 86% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  SZ-047 is 86% of 25837 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  6 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
