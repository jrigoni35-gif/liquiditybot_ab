# Session digest

**Verdict: SD-002 model starvation loop**

- Window: 2026-07-10 07:53 UTC -> 2026-07-21 09:42 UTC (265.81h, ~985 cycles)
- Equity: $25,000.00 -> $4,992.62 (range $99,208.70) | realized PnL $-3.80 | fees $8.44
- Activity: 3 open | 88 live labeled trades | 2161 candidates | 76 postmortems
- Model: level 2 | use_model=False | brier n/a | history_rows 88 | cold=True
- Audit: 1465 records (658 non-routine) | dominant OM-000 (32% of non-routine) | chain_ok=False (tamper=False, seams=2) | retrain_requests 26
- Liquidity: spoofy 35% of classified cycles | feed errors 0

## Diagnostics
- [WARN] **SD-002 model starvation loop**  -  model is cold (live training rows=88, brier=n/a) yet retrain was requested 26x  -  with 0 entries there is no new data, so retraining can never clear the condition. Seed a model (scripts/train_meta.py) or supply history; this loop is also 32% of the audit trail
- [WARN] **SD-004 audit trail dominated by one code**  -  OM-000 is 32% of 658 non-routine records  -  consequential dispositions are buried; rate-limit that emitter
- [INFO] **SD-010 audit writer seam(s)**  -  2 hash-valid concurrent-writer fork(s) in the chain - benign (no committed record altered); prevention: runner instance lock + one-bot mode
