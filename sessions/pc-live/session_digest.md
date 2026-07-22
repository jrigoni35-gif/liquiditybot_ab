# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-22 02:42 UTC (282.81h, ~840 cycles)
- Equity: $25,000.00 -> $4,989.57 (range $99,208.70) | realized PnL $-5.52 | fees $11.54
- Activity: 2 open | 108 live labeled trades | 2319 candidates | 92 postmortems
- Model: level 0 | use_model=True | brier n/a | history_rows 108 | cold=True
- Audit: 1940 records (778 non-routine) | dominant OM-000 (33% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 29
- Liquidity: spoofy 31% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=108, brier=n/a) yet retrain was requested 29x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 33% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 33% of 778 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
